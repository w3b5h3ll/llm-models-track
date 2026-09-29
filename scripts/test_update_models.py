import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import update_models as m


class ModelWatchTests(unittest.TestCase):
    def setUp(self):
        self.payload = {"data": [
            {"id": "lab/model-4.20", "created": 10, "context_length": 100},
            {"id": "lab/model-4.7", "created": 20, "context_length": 200},
            {"id": "lab/model-4.7:batch", "created": 30},
        ]}
        self.rule = {"provider": "lab", "match": "lab/model-*", "exclude": ["*:*"]}

    def test_latest_uses_date_and_excludes_channel_variants(self):
        rows = m.resolve("openrouter", self.payload, [{**self.rule, "latest": 1}])
        self.assertEqual([r["id"] for r in rows], ["lab/model-4.7"])

    def test_family_discovers_new_models_and_deduplicates(self):
        exact = {"provider": "lab", "id": "lab/model-4.7"}
        self.assertEqual(len(m.resolve("openrouter", self.payload, [self.rule, exact])), 2)
        self.payload["data"].append({"id": "lab/model-5", "created": 40})
        self.assertEqual(len(m.resolve("openrouter", self.payload, [self.rule])), 3)

    def test_unknown_capabilities_are_null(self):
        row = m.normalize("openrouter", self.payload, [{"provider": "lab", "id": "lab/model-4.7"}])[0]
        self.assertIsNone(row["tool_call"])
        self.assertIsNone(row["max_input_tokens"])

    def test_latest_family_keeps_variants_and_ignores_old_family_updates(self):
        payload = {"data": [
            {"id": "x-ai/grok-4.20", "created": 10},
            {"id": "x-ai/grok-4.20-fast", "created": 50},
            {"id": "x-ai/grok-4.7", "created": 20},
            {"id": "x-ai/grok-4.7-fast", "created": 30},
            {"id": "x-ai/grok-4.7:batch", "created": 40},
            {"id": "x-ai/grok-build-0.1", "created": 60},
        ]}
        rule = {"provider": "x-ai", "match": "x-ai/grok-*", "exclude": ["*:*"] ,
                "latest_family": r"^(x-ai/grok-[0-9]+(?:\.[0-9]+)*)(?:-|$)"}
        rows = m.resolve("openrouter", payload, [rule])
        self.assertEqual({r["id"] for r in rows}, {"x-ai/grok-4.7", "x-ai/grok-4.7-fast"})
        payload["data"].append({"id": "x-ai/grok-5", "created": 70})
        self.assertEqual([r["id"] for r in m.resolve("openrouter", payload, [rule])], ["x-ai/grok-5"])

    def test_models_dev_provider_lookup_and_date(self):
        payload = {"lab": {"models": {"a": {"release_date": "2026-01-01", "limit": {"context": 300},
                    "modalities": {"input": ["audio"]}, "tool_call": False}}}}
        watched = m.resolve("models.dev", payload, [{"provider": "lab", "match": "*", "latest": 1}])
        row = m.normalize("models.dev", payload, watched)[0]
        self.assertEqual(row["context_tokens"], 300)
        self.assertEqual(row["input_modalities"], ["audio"])
        self.assertIs(row["tool_call"], False)

    def test_unchanged_output_and_failure_preserve_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, out = Path(tmp) / "watchlist.json", Path(tmp) / "data"
            config.write_text(json.dumps({"source": "openrouter", "models": [self.rule]}))
            with patch.object(sys, "argv", ["update", "--config", str(config), "--output-dir", str(out)]), \
                    patch.object(m, "fetch", return_value=self.payload):
                m.main()
                before = {f.name: f.read_bytes() for f in out.iterdir()}
                m.main()
                self.assertEqual(before, {f.name: f.read_bytes() for f in out.iterdir()})
                config.write_text(json.dumps({"source": "openrouter", "models": [
                    {"provider": "lab", "id": "lab/missing"}]}))
                with self.assertRaises(ValueError):
                    m.main()
                self.assertEqual(before, {f.name: f.read_bytes() for f in out.iterdir()})


if __name__ == "__main__":
    unittest.main()
