"""Token 薅羊毛活动：发现（LLM 抽取）+ 核实（quote 复核）。Python 3.11+，仅标准库。

设计原则与 official_sources.py 一致：
- LLM 只做发现与结构化抽取，不做事实裁决；每条候选必须带可验证的逐字原文 quote。
- quote 由确定性代码在重新抓取的页面上复核；复核不过的候选不会进入发布数据。
- 已收录活动每次运行重新核实：quote 消失 → 核实失败（保留旧证据并标 stale）；
  ends_at 已过 → 已结束；抓取失败 → 保留旧快照。
- 人工确认（把条目写进 deals.json 的 deals 列表）是候选进入正式名单的唯一途径。
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from official_sources import fetch_page

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LLM_ENDPOINT = "https://api.z.ai/api/paas/v4/chat/completions"
DEFAULT_LLM_MODEL = "glm-5.3-flash"

PENDING_KINDS = ("free_tier", "free_model", "discount", "limited_time_free", "credits")

SYSTEM_PROMPT = """你是 AI API 平台优惠活动的信息抽取器。输入是一个网页的文本内容。
只抽取明确写在页面上的优惠/羊毛信息（免费模型、免费额度、赠送 tokens、错峰折扣、限时免费等）。
要求：
- 每条抽取结果必须附 quote 字段：从输入文本中逐字复制的原文片段（连续、不做改写，60~300 字符）。
- 没有优惠信息就返回空数组；不要编造、不要推测、不要把普通价格表当成优惠。
- ends_at 只在页面明确写出截止日期时填 ISO 日期，否则填 null。
- 输出严格的 JSON 数组，每项字段：
  title（简短中文标题）、kind（free_tier|free_model|discount|limited_time_free|credits 之一）、
  reward（一句话说明权益）、claim_steps（如何领取/使用，一句话）、
  eligibility（适用对象，一句话）、ends_at（ISO 日期或 null）、quote（原文片段）。
只输出 JSON 数组，不要其他文字。"""

USER_TEMPLATE = """页面地址：{url}
关注方向：{hint}
请抽取该页面上的优惠信息（没有则返回 []）。

页面文本：
{page}"""


def call_llm(endpoint, model, api_key, page_text, url, hint, timeout=90):
    """调用 OpenAI 兼容接口做抽取；返回解析后的候选列表。失败抛异常。"""
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_TEMPLATE.format(url=url, hint=hint, page=page_text)},
        ],
        "temperature": 0,
        "max_tokens": 2000,
    }).encode()
    request = urllib.request.Request(endpoint, data=body, headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
        "User-Agent": "model-watch/1.0",
    })
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError(f"LLM 端点返回非 JSON（开头 {raw[:60]!r}），检查端点/密钥/模型名")
    content = payload["choices"][0]["message"]["content"]
    match = re.search(r'\[.*\]', content, re.S)
    if not match:
        raise ValueError("LLM 返回中找不到 JSON 数组")
    candidates = json.loads(match.group(0))
    if not isinstance(candidates, list):
        raise ValueError("LLM 返回不是 JSON 数组")
    return candidates


def quote_in_page(quote, page):
    """quote 复核：原文片段（按任意空白切分后）必须逐段出现在页面上。"""
    pattern = r'\s+'.join(re.escape(part) for part in quote.split())
    return bool(re.search(pattern, page, re.I))


def stable_pending_id(source_id, title):
    """候选 ID 必须跨进程稳定。内置 hash() 受 PYTHONHASHSEED 影响，不能用来做发布数据的主键。"""
    digest = hashlib.sha256(f"{source_id}\n{title.strip()}".encode()).hexdigest()[:10]
    return f"pending-{source_id}-{digest}"


def repeats_confirmed(candidate, confirmed):
    """同一来源页上、原文互相包含的候选视为已收录，不再放进待确认。"""
    quote = candidate["evidence"]["quote"]
    url = candidate["evidence"]["url"]
    for deal in confirmed or []:
        evidence = deal.get("evidence") or {}
        known = evidence.get("quote")
        if evidence.get("url") != url or not known:
            continue
        if quote_in_page(known, quote) or quote_in_page(quote, known):
            return True
    return False


def normalize_candidate(raw, source, now):
    """把 LLM 候选整理成 pending 记录；缺关键字段或 quote 过短时丢弃。"""
    if not isinstance(raw, dict):
        return None
    quote = raw.get("quote")
    if not isinstance(quote, str) or len(quote.strip()) < 12:
        return None
    kind = raw.get("kind")
    if kind not in PENDING_KINDS:
        return None
    title = str(raw.get("title") or "").strip()
    if not title:
        return None
    ends = raw.get("ends_at")
    if isinstance(ends, str) and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", ends):
        ends = None
    return {
        "id": stable_pending_id(source["id"], title),
        "provider": source["provider"],
        "title": title,
        "kind": kind,
        "reward": str(raw.get("reward") or "").strip(),
        "claim_url": source["url"],
        "claim_steps": str(raw.get("claim_steps") or "").strip(),
        "eligibility": str(raw.get("eligibility") or "").strip(),
        "ends_at": ends,
        "source_id": source["id"],
        "evidence": {"url": source["url"], "quote": quote.strip()[:1200]},
        "discovered_at": now,
    }


def verify_confirmed(deals, pages, previous, now):
    """对已收录活动逐条核实，产出发布记录与检查状态。

    quote 仍在页面 → active；页面变了 quote 没了 → 保留旧记录标 stale；
    抓取失败 → 保留旧记录标 stale；ends_at 已过 → expired（无论 quote 是否还在）。
    """
    previous_by_id = {deal["id"]: deal for deal in (previous or [])}
    result, checks = [], {}
    for deal in deals:
        row = dict(deal)
        source_page = pages.get(deal["evidence"]["url"])
        if source_page is None:
            row["status"] = "stale"
            row["note"] = "本次无法访问来源页面，保留上次核实的证据"
            check = {"status": "failed", "message": "来源页面暂时无法访问"}
        else:
            if deal.get("ends_at") and deal["ends_at"] < now[:10]:
                row["status"] = "expired"
                row["note"] = f"活动截止（{deal['ends_at']}）"
                check = {"status": "verified", "message": "活动已过截止日期"}
            elif quote_in_page(deal["evidence"]["quote"], source_page):
                row["status"] = "active"
                row["note"] = ""
                check = {"status": "verified"}
            else:
                row["status"] = "stale"
                row["note"] = "官方页面已找不到活动原文，请人工复核或移除"
                check = {"status": "failed", "message": "evidence quote 不在当前页面上"}
        previous_deal = previous_by_id.get(deal["id"])
        if previous_deal and previous_deal.get("status") == row["status"] and not check.get("message"):
            row["verified_at"] = previous_deal.get("verified_at", now)
        else:
            row["verified_at"] = now
        result.append(row)
        checks[deal["id"]] = check
    return result, checks


def discover(sources, llm_config, keywords, loader=fetch_page, extractor=None, confirmed=None):
    """抓取来源页，运行 LLM 抽取并复核 quote；只发布复核通过的候选。"""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    pages = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(loader, source["url"]): source for source in sources}
        for future in concurrent.futures.as_completed(futures):
            source = futures[future]
            try:
                content = future.result()
            except Exception:
                content = None
            pages[source["id"]] = content
    candidates, checks = [], {}
    for source in sources:
        page = pages[source["id"]]
        if page is None:
            checks[source["id"]] = {"status": "failed", "message": "来源页面暂时无法访问"}
            continue
        checks[source["id"]] = {"status": "verified"}
        lowered = page.lower()
        if not any(keyword.lower() in lowered for keyword in keywords):
            checks[source["id"]].update({"status": "no_deals", "message": "页面未出现优惠关键词，跳过 LLM"})
            continue
        try:
            raw_candidates = extractor(page, source) if extractor else call_llm(
                llm_config["endpoint"], llm_config["model"], llm_config["api_key"],
                page[:llm_config["max_page_chars"]], source["url"], source.get("hint", ""))
        except Exception as error:
            checks[source["id"]] = {"status": "failed", "message": f"LLM 抽取失败：{error}"}
            continue
        accepted = 0
        seen = {item["id"] for item in candidates}
        for raw in raw_candidates:
            candidate = normalize_candidate(raw, source, now)
            if not candidate or candidate["id"] in seen:
                continue
            if not quote_in_page(candidate["evidence"]["quote"], page):
                continue
            if repeats_confirmed(candidate, confirmed):
                continue
            candidates.append(candidate)
            seen.add(candidate["id"])
            accepted += 1
        checks[source["id"]]["candidates"] = accepted
    return candidates, checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", type=Path, default=ROOT / "deals_sources.json")
    parser.add_argument("--deals", type=Path, default=ROOT / "deals.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--skip-llm", action="store_true",
                        help="跳过发现阶段，只核实已收录活动（本地预览/无 token 环境）")
    args = parser.parse_args()

    sources_config = json.loads(args.sources.read_text())
    deals_config = json.loads(args.deals.read_text())
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    confirmed = deals_config.get("deals", [])
    for deal in confirmed:
        if not all(deal.get(key) for key in ("id", "provider", "title", "claim_url")) or not deal.get("evidence", {}).get("quote"):
            raise ValueError(f"deals.json 条目字段不完整：{deal.get('id', '(无 id)')}，需要 id/provider/title/claim_url/evidence.quote")

    previous_path = args.output_dir / "deals.json"
    previous = json.loads(previous_path.read_text()).get("deals", []) if previous_path.exists() else []

    # 已收录活动核实与 LLM 发现有相同的来源 URL 时共用一次抓取。
    loader = fetch_page
    cache = {}
    source_urls = [source["url"] for source in sources_config["sources"]]
    evidence_urls = [deal["evidence"]["url"] for deal in confirmed]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(loader, url): url for url in dict.fromkeys(source_urls + evidence_urls)}
        for future in concurrent.futures.as_completed(futures):
            try:
                cache[futures[future]] = future.result()
            except Exception:
                pass

    def cached_loader(url):
        page = cache.get(url)
        if page is not None:
            return page
        result = loader(url)
        cache[url] = result
        return result

    pending, discover_checks = [], {}
    if not args.skip_llm:
        llm_config = dict(sources_config.get("llm", {}))
        llm_config["endpoint"] = os.environ.get("LLM_ENDPOINT") or llm_config.get("endpoint") or DEFAULT_LLM_ENDPOINT
        llm_config["model"] = os.environ.get("LLM_MODEL") or llm_config.get("model") or DEFAULT_LLM_MODEL
        llm_config["max_page_chars"] = int(llm_config.get("max_page_chars", 12000))
        llm_config["api_key"] = os.environ.get("LLM_API_KEY") or llm_config.get("api_key")
        if not llm_config["api_key"]:
            print("::warning::缺少 LLM_API_KEY，跳过 LLM 发现阶段，仅核实已收录活动")
            args.skip_llm = True
        else:
            pending, discover_checks = discover(
                sources_config["sources"], llm_config, sources_config.get("keywords", []),
                loader=cached_loader, confirmed=confirmed)

    verified, checks = verify_confirmed(
        confirmed, {url: cache.get(url) for url in evidence_urls}, previous, now)

    document = {
        "checked_at": now,
        "deals": verified,
        "pending": pending,
        "pending_note": "" if pending else "待确认候选为空：确认后的活动请写入 deals.json 的 deals 列表",
        "discover_checks": discover_checks,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "deals.json").write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    (args.output_dir / "deals_checks.json").write_text(json.dumps(
        {"checked_at": now, "deals": checks}, ensure_ascii=False, indent=2) + "\n")

    counts = {}
    for row in verified:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    status = f"活动核实：{counts or '无已收录活动'}；待确认候选：{len(document['pending'])}"
    print(status)
    if failed := [k for k, v in checks.items() if v["status"] == "failed"]:
        print(f"::warning::以下活动核实失败，已保留旧快照并标记 stale：{', '.join(failed)}")
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a") as handle:
            handle.write(status + "\n")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as error:
        print(f"活动采集失败：{error}", file=sys.stderr)
        sys.exit(1)
