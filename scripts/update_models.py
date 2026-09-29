"""Fetch only watched model metadata. Python 3.11+, standard library only."""
import argparse
import fnmatch
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from official_sources import enrich

ROOT = Path(__file__).resolve().parents[1]
URLS = {
    "openrouter": "https://openrouter.ai/api/v1/models",
    "models.dev": "https://models.dev/api.json",
}


def fetch(url):
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={
                "User-Agent": "model-watch/1.0", "Accept": "application/json"
            })
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def normalize(source, payload, watched):
    rows = []
    for entry in watched:
        provider, model_id = entry["provider"], entry["id"]
        if source == "openrouter":
            model = next((m for m in payload["data"] if m["id"] == model_id), None)
        else:
            model = payload.get(provider, {}).get("models", {}).get(model_id)
        if model is None:
            raise ValueError(f"找不到模型：{provider} / {model_id}；旧数据未更新。请检查 ID 或来源。")
        if source == "openrouter":
            modalities = model.get("architecture") or {}
            limits = model.get("top_provider") or {}
            parameters = model.get("supported_parameters")
            values = {
                "context_tokens": model.get("context_length"),
                "max_input_tokens": None,
                "max_output_tokens": limits.get("max_completion_tokens"),
                "input_modalities": modalities.get("input_modalities"),
                "output_modalities": modalities.get("output_modalities"),
                "tool_call": None if parameters is None else "tools" in parameters,
                "reasoning": None if parameters is None else "reasoning" in parameters,
            }
            scope = "OpenRouter model catalog; output limit from top_provider"
        else:
            limits = model.get("limit") or {}
            modalities = model.get("modalities") or {}
            values = {
                "context_tokens": limits.get("context"),
                "max_input_tokens": limits.get("input"),
                "max_output_tokens": limits.get("output"),
                "input_modalities": modalities.get("input"),
                "output_modalities": modalities.get("output"),
                "tool_call": model.get("tool_call"),
                "reasoning": model.get("reasoning"),
            }
            scope = f"Models.dev provider entry: {provider}"
        rows.append({
            "provider": provider, "id": model_id,
            "name": model.get("name", model_id),
            "source": URLS[source], "scope": scope, **values,
        })
    return sorted(rows, key=lambda row: (row["provider"], row["id"]))


def resolve(source, payload, rules):
    """Expand exact IDs and glob rules; latest means catalog date, not name order."""
    selected = {}
    for rule in rules:
        provider = rule["provider"]
        if not isinstance(provider, str) or not provider.strip():
            raise ValueError("provider 必须是非空字符串")
        if ("id" in rule) == ("match" in rule):
            raise ValueError("每条规则必须且只能指定 id 或 match")
        pattern = rule.get("id", rule.get("match"))
        if not isinstance(pattern, str) or not pattern.strip():
            raise ValueError("id 或 match 必须是非空字符串")
        excludes = rule.get("exclude", [])
        if not isinstance(excludes, list) or any(not isinstance(x, str) for x in excludes):
            raise ValueError("exclude 必须是字符串列表")
        if source == "openrouter":
            catalog = {m["id"]: m for m in payload["data"]}
        else:
            catalog = payload.get(provider, {}).get("models", {})
        matches = [(key, model) for key, model in catalog.items()
                   if (key == pattern if "id" in rule else fnmatch.fnmatchcase(key, pattern))
                   and not any(fnmatch.fnmatchcase(key, x) for x in excludes)]
        if not matches:
            raise ValueError(f"规则未匹配任何模型：{provider} / {pattern}；旧数据未更新。")
        if "latest" in rule and "latest_family" in rule:
            raise ValueError("latest 和 latest_family 不能同时使用")
        if "latest_family" in rule:
            regex = re.compile(rule["latest_family"])
            if regex.groups != 1:
                raise ValueError("latest_family 必须包含一个捕获组，用于提取系列 ID")
            field = "created" if source == "openrouter" else "release_date"
            families = {}
            for key, model in matches:
                match = regex.search(key)
                if match:
                    if not model.get(field):
                        raise ValueError(f"无法按最新系列排序：{key} 缺少 {field}")
                    families.setdefault(match.group(1), []).append((key, model))
            if not families:
                raise ValueError(f"无法识别模型系列：{pattern}")
            # 按系列首次收录日期选择，避免旧系列新增变体挤掉新系列。
            newest = max(families, key=lambda family: (
                min(model[field] for _, model in families[family]), family))
            matches = families[newest]
        if "latest" in rule:
            count = rule["latest"]
            if type(count) is not int or count < 1:
                raise ValueError("latest 必须是正整数")
            field = "created" if source == "openrouter" else "release_date"
            if any(not model.get(field) for _, model in matches):
                raise ValueError(f"无法按最新排序：候选模型缺少 {field}")
            matches.sort(key=lambda pair: (pair[1][field], pair[0]), reverse=True)
            matches = matches[:count]
        for key, _ in matches:
            selected[(provider, key)] = {"provider": provider, "id": key}
    return list(selected.values())


def cell(value):
    if value is None:
        return "未知"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, list):
        value = ", ".join(value)
    return str(value).replace("|", "\\|").replace("\n", " ")


def render(document):
    lines = ["# 关注模型参数", "",
             f"数据最后变更采集时间（UTC）：{document['changed_at']}", "",
             "每次检查的时间见 Actions 日志；下表仅在数据变化时更新。未知表示来源未提供。", "",
             "| 模型 ID | 上下文 tokens | 最大输入 | 最大输出 | 输入模态 | 输出模态 | 工具调用 | 推理 | 规格来源 |",
             "| --- | ---: | --- | ---: | --- | --- | --- | --- | --- |"]
    fields = ["id", "context_tokens", "max_input_tokens", "max_output_tokens",
              "input_modalities", "output_modalities", "tool_call", "reasoning"]
    for row in document["models"]:
        cells = [cell(row.get(key)) for key in fields]
        if row.get('max_input_tokens_thinking') is not None:
            cells[2] = f"思考 {cell(row['max_input_tokens_thinking'])}；非思考 {cell(row.get('max_input_tokens_non_thinking'))}"
        label = '官方' if row.get('basis') == 'official' else '聚合平台'
        if (row.get('official') or {}).get('status') == 'stale':
            label += '（旧快照）'
        lines.append("| " + " | ".join(cells) + f" | [{label}]({row['source']}) |")
    lines.extend(["", "优先显示同型号的官方规格，官方未列字段不使用平台值补齐。未核实官方规格的条目标为聚合平台。", "",
                  "K/M 为官方简写时保留原文，数值按十进制展开用于排序。Qwen 权重模型显示原生上下文，扩展能力见 JSON / 网页详情。", "",
                  "原始平台规格及逐字段官方证据见 models.json；每次检查状态见 checks.json（随网页发布）。", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "watchlist.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    source, watched = config["source"], config["models"]
    if source not in URLS:
        raise ValueError("source 必须为 openrouter 或 models.dev")
    if not isinstance(watched, list) or not watched:
        raise ValueError("models 必须是非空列表")
    payload = fetch(URLS[source])
    rows = normalize(source, payload, resolve(source, payload, watched))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    path = args.output_dir / "models.json"
    old = json.loads(path.read_text()) if path.exists() else {}
    checks = None
    if config.get('official_sources'):
        official_config = json.loads((args.config.parent / config['official_sources']).read_text())
        rows, checks = enrich(rows, official_config, old.get('models', []))
    changed = old.get("models") != rows
    document = {
        "source_url": URLS[source],
        "changed_at": now if changed else old["changed_at"],
        "models": rows,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    markdown = render(document)
    (args.output_dir / "models.md").write_text(markdown)
    if checks:
        (args.output_dir / 'checks.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2) + '\n')
        counts = {status: sum(r['status'] == status for r in checks['models'].values())
                  for status in ('verified', 'failed', 'not_configured')}
        print(f"官方核对：{counts}")
        if counts['failed']:
            print('::warning::部分官方来源核对失败，已保留旧证据或明确回退到平台数据；见 checks.json')
    status = f"检查时间：{now}；关注 {len(rows)} 个模型；" + ("数据有变化" if changed else "数据无变化")
    print(status)
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a") as handle:
            handle.write(status + "\n\n" + markdown)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(f"采集失败：{error}", file=sys.stderr)
        sys.exit(1)
