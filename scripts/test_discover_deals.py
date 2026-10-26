import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import discover_deals as m


class QuoteCheckTests(unittest.TestCase):
    def test_quote_matches_despite_whitespace_changes(self):
        page = 'Free usage limits:\n  If  you’re using a free model variant (with an ID\nending in :free), the following limits apply:'
        self.assertTrue(m.quote_in_page('Free usage limits: If you’re using a free model variant', page))

    def test_quote_fails_when_page_rewritten(self):
        self.assertFalse(m.quote_in_page('半价优惠', '页面已改版，没有这条内容'))


class NormalizeCandidateTests(unittest.TestCase):
    def setUp(self):
        self.source = {"id": "src", "url": "https://example.com", "provider": "lab"}
        self.raw = {"title": "新用户赠 1000 万 tokens", "kind": "credits", "reward": "1000 万 tokens",
                    "claim_steps": "注册后领取", "eligibility": "新用户", "ends_at": None,
                    "quote": "注册即赠 1000 万 tokens，有效期 90 天"}

    def test_valid_candidate_keeps_required_fields(self):
        row = m.normalize_candidate(self.raw, self.source, "2026-01-01T00:00:00+00:00")
        again = m.normalize_candidate(self.raw, self.source, "2026-01-01T00:00:00+00:00")
        self.assertEqual(row["provider"], "lab")
        self.assertEqual(row["kind"], "credits")
        self.assertEqual(row["evidence"]["quote"], self.raw["quote"])
        self.assertEqual(row["discovered_at"], "2026-01-01T00:00:00+00:00")
        self.assertEqual(row["id"], again["id"])
        self.assertTrue(row["id"].startswith("pending-src-"))

    def test_rejects_short_or_missing_quote(self):
        self.assertIsNone(m.normalize_candidate({**self.raw, "quote": "太短"}, self.source, ""))
        self.assertIsNone(m.normalize_candidate({**self.raw, "quote": None}, self.source, ""))

    def test_rejects_unknown_kind_and_empty_title(self):
        self.assertIsNone(m.normalize_candidate({**self.raw, "kind": "mystery"}, self.source, ""))
        self.assertIsNone(m.normalize_candidate({**self.raw, "title": " "}, self.source, ""))

    def test_bad_ends_at_is_dropped_not_error(self):
        row = m.normalize_candidate({**self.raw, "ends_at": "明年年底"}, self.source, "")
        self.assertIsNone(row["ends_at"])


def deal(quote, ends_at=None, deal_id="lab-deal"):
    return {"id": deal_id, "provider": "lab", "title": "活动", "kind": "credits",
            "reward": "tokens", "claim_url": "https://example.com", "claim_steps": "领取",
            "eligibility": "所有人", "ends_at": ends_at,
            "evidence": {"url": "https://example.com", "quote": quote}}


class VerifyConfirmedTests(unittest.TestCase):
    def setUp(self):
        self.now = "2026-10-19T00:00:00+00:00"
        self.deal = deal("注册即赠 1000 万 tokens")

    def test_active_when_quote_still_on_page(self):
        rows, checks = m.verify_confirmed([self.deal], {"https://example.com": "公告：注册即赠 1000 万 tokens，先到先得"}, [], self.now)
        self.assertEqual(rows[0]["status"], "active")
        self.assertEqual(checks[self.deal["id"]]["status"], "verified")

    def test_stale_when_quote_disappears_and_old_record_kept(self):
        previous = [{**self.deal, "status": "active", "verified_at": "2026-10-01T00:00:00+00:00"}]
        rows, checks = m.verify_confirmed([self.deal], {"https://example.com": "页面已改版"}, previous, self.now)
        self.assertEqual(rows[0]["status"], "stale")
        self.assertEqual(checks[self.deal["id"]]["status"], "failed")

    def test_stale_when_fetch_fails_and_previous_preserved(self):
        previous = [{**self.deal, "status": "active", "verified_at": "2026-10-01T00:00:00+00:00"}]
        rows, checks = m.verify_confirmed([self.deal], {"https://example.com": None}, previous, self.now)
        self.assertEqual(rows[0]["status"], "stale")
        self.assertEqual(checks[self.deal["id"]]["status"], "failed")

    def test_expired_by_ends_at_even_if_quote_remains(self):
        expired = deal("注册即赠 1000 万 tokens", ends_at="2026-10-01", deal_id="old")
        rows, checks = m.verify_confirmed([expired], {"https://example.com": "注册即赠 1000 万 tokens"}, [], self.now)
        self.assertEqual(rows[0]["status"], "expired")
        self.assertEqual(checks["old"]["status"], "verified")

    def test_verified_at_stays_stable_when_nothing_changed(self):
        first = {**self.deal, "status": "active", "verified_at": "2026-10-01T00:00:00+00:00"}
        rows_a, _ = m.verify_confirmed([self.deal], {"https://example.com": "注册即赠 1000 万 tokens"}, [first], self.now)
        self.assertEqual(rows_a[0]["verified_at"], "2026-10-01T00:00:00+00:00")
        rows_b, _ = m.verify_confirmed([self.deal], {"https://example.com": "注册即赠 1000 万 tokens"}, [], self.now)
        self.assertEqual(rows_b[0]["verified_at"], self.now)


class DiscoverTests(unittest.TestCase):
    def setUp(self):
        self.sources = [{"id": "src", "url": "https://example.com", "provider": "lab", "hint": "优惠"}]
        self.llm = {"endpoint": "https://llm.example", "model": "test", "api_key": "k", "max_page_chars": 5000}

    def test_candidates_require_verified_quote(self):
        pages = {"https://example.com": "注册即赠 1000 万 tokens，先到先得"}
        def extractor(page, source):
            return [{"title": "赠 tokens", "kind": "credits", "reward": "1000 万", "quote": "注册即赠 1000 万 tokens"},
                    {"title": "幻觉活动", "kind": "credits", "reward": "不存在", "quote": "这句话页面上根本没有"}]
        candidates, checks = m.discover(self.sources, self.llm, ["赠"], loader=lambda url: pages[url], extractor=extractor)
        self.assertEqual([c["title"] for c in candidates], ["赠 tokens"])
        self.assertEqual(checks["src"]["status"], "verified")
        self.assertEqual(checks["src"]["candidates"], 1)

    def test_keyword_gate_skips_llm_without_hits(self):
        candidates, checks = m.discover(self.sources, self.llm, ["羊毛"], loader=lambda url: "普通价格表", extractor=lambda *_: [])
        self.assertEqual(candidates, [])
        self.assertEqual(checks["src"]["status"], "no_deals")

    def test_llm_error_marks_source_failed(self):
        def extractor(page, source):
            raise ValueError("LLM 返回不是 JSON 数组")
        candidates, checks = m.discover(self.sources, self.llm, ["赠"], loader=lambda url: "赠送", extractor=extractor)
        self.assertEqual(candidates, [])
        self.assertEqual(checks["src"]["status"], "failed")

    def test_confirmed_quote_is_not_reproposed(self):
        pages = {"https://example.com": "公告：注册即赠 1000 万 tokens，先到先得"}
        confirmed = [deal("注册即赠 1000 万 tokens")]
        confirmed[0]["evidence"]["url"] = "https://example.com"
        def extractor(page, source):
            return [{"title": "赠 tokens", "kind": "credits", "reward": "1000 万", "quote": "注册即赠 1000 万 tokens"},
                    {"title": "另一档优惠", "kind": "discount", "reward": "半价", "quote": "周末调用半价，无需额外领取"}]
        candidates, checks = m.discover(
            self.sources, self.llm, ["赠", "半价"], loader=lambda url: pages[url] + "\n周末调用半价，无需额外领取",
            extractor=extractor, confirmed=confirmed)
        self.assertEqual([c["title"] for c in candidates], ["另一档优惠"])
        self.assertEqual(checks["src"]["candidates"], 1)

    def test_fetch_failure_marks_source_failed(self):
        def loader(url):
            raise OSError("timeout")
        candidates, checks = m.discover(self.sources, self.llm, ["赠"], loader=loader, extractor=lambda *_: [])
        self.assertEqual(candidates, [])
        self.assertEqual(checks["src"]["status"], "failed")


class MainTests(unittest.TestCase):
    def setUp(self):
        self.deal = deal("注册即赠 1000 万 tokens")
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "deals_sources.json").write_text(json.dumps({
            "llm": {"endpoint": "https://llm.example", "model": "test", "max_page_chars": 100},
            "keywords": ["赠"],
            "sources": [{"id": "src", "url": "https://example.com", "provider": "lab", "hint": ""}]}))
        (root / "deals.json").write_text(json.dumps({"deals": [self.deal]}))
        self.root, self.out = root, root / "data"

    def tearDown(self):
        self.tmp.cleanup()

    def test_main_writes_verified_data_and_is_stable_without_changes(self):
        def loader(url):
            return "公告：注册即赠 1000 万 tokens，先到先得"
        with patch.object(m, "fetch_page", loader), patch.object(sys, "argv", ["x", "--sources", str(self.root / "deals_sources.json"), "--deals", str(self.root / "deals.json"), "--output-dir", str(self.out), "--skip-llm"]):
            m.main()
            first = {p.name: p.read_bytes() for p in self.out.iterdir()}
            m.main()
            self.assertEqual(first, {p.name: p.read_bytes() for p in self.out.iterdir()})
        document = json.loads((self.out / "deals.json").read_text())
        self.assertEqual(document["deals"][0]["status"], "active")

    def test_main_preserves_stale_snapshot_when_page_changes(self):
        with patch.object(m, "fetch_page", lambda url: "页面已改版"), patch.object(sys, "argv", ["x", "--sources", str(self.root / "deals_sources.json"), "--deals", str(self.root / "deals.json"), "--output-dir", str(self.out), "--skip-llm"]):
            m.main()
        document = json.loads((self.out / "deals.json").read_text())
        self.assertEqual(document["deals"][0]["status"], "stale")
        self.assertEqual(document["deals"][0]["evidence"]["quote"], self.deal["evidence"]["quote"])
        checks = json.loads((self.out / "deals_checks.json").read_text())
        self.assertEqual(checks["deals"][self.deal["id"]]["status"], "failed")

    def test_main_rejects_incomplete_deal_entries(self):
        (self.root / "deals.json").write_text(json.dumps({"deals": [{"id": "broken"}]}))
        with patch.object(sys, "argv", ["x", "--sources", str(self.root / "deals_sources.json"), "--deals", str(self.root / "deals.json"), "--output-dir", str(self.out), "--skip-llm"]):
            with self.assertRaises(ValueError):
                m.main()


if __name__ == "__main__":
    unittest.main()
