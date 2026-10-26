import copy
import json
import unittest
from pathlib import Path

from official_sources import enrich, parse_rule, page_text


class OfficialTests(unittest.TestCase):
    def setUp(self):
        self.rule = {'url': 'https://official.example/model', 'official_model_id': 'model-1',
                     'scope': '官方 API', 'requires': ['Model One'], 'fields': {
                         'context_tokens': {'type': 'tokens', 'pattern': r'Context: (?P<value>[0-9]+K)'},
                         'max_output_tokens': {'type': 'tokens', 'pattern': r'Output: (?P<value>[0-9]+K)'}}}
        self.config = {'models': {'lab/model-1': self.rule}}
        self.platform = {'id': 'lab/model-1', 'provider': 'lab', 'name': 'Model One',
                         'source': 'https://relay.example', 'scope': 'relay',
                         'context_tokens': 999999, 'max_input_tokens': 55555, 'max_output_tokens': 88888,
                         'input_modalities': ['image'], 'output_modalities': ['text'], 'tool_call': True}
        self.text = 'Model One\nContext: 128K\nOutput: 16K'

    def test_official_priority_without_cross_source_gap_filling(self):
        rows, checks = enrich([self.platform], self.config, loader=lambda _: self.text)
        model = rows[0]
        self.assertEqual(model['context_tokens'], 128000)
        self.assertIsNone(model['max_input_tokens'])
        self.assertIsNone(model['input_modalities'])
        self.assertEqual(model['platform']['max_input_tokens'], 55555)
        self.assertEqual(model['official']['field_sources']['context_tokens']['reported'], '128K')
        self.assertEqual(checks['models'][model['id']]['status'], 'verified')

    def test_failed_refresh_preserves_verified_evidence_and_marks_stale(self):
        old, _ = enrich([self.platform], self.config, loader=lambda _: self.text)
        rows, checks = enrich([self.platform], self.config, old, loader=lambda _: 'layout changed')
        self.assertEqual(rows[0]['max_output_tokens'], 16000)
        self.assertEqual(rows[0]['official']['status'], 'stale')
        self.assertEqual(checks['models'][rows[0]['id']]['status'], 'failed')

    def test_new_model_is_not_given_another_models_official_evidence(self):
        old, _ = enrich([self.platform], self.config, loader=lambda _: self.text)
        new = {**self.platform, 'id': 'lab/model-2'}
        rows, _ = enrich([new], self.config, old, loader=lambda _: self.text)
        self.assertEqual(rows[0]['basis'], 'platform')
        self.assertIsNone(rows[0]['official'])

    def test_new_mapping_does_not_reuse_old_source_on_failure(self):
        old, _ = enrich([self.platform], self.config, loader=lambda _: self.text)
        config = copy.deepcopy(self.config)
        config['models']['lab/model-1']['official_model_id'] = 'different-model'
        rows, _ = enrich([self.platform], config, old, loader=lambda _: '')
        self.assertIsNone(rows[0]['official'])

    def test_check_timestamps_do_not_cause_model_data_changes(self):
        first, _ = enrich([self.platform], self.config, loader=lambda _: self.text)
        second, _ = enrich([self.platform], self.config, first, loader=lambda _: self.text)
        self.assertEqual(first, second)

    def test_conflicting_values_are_rejected(self):
        with self.assertRaises(ValueError):
            parse_rule(self.rule, self.text + '\nContext: 256K')

    def test_input_limits_keep_thinking_modes_separate(self):
        rule = copy.deepcopy(self.rule)
        rule['fields']['max_input_tokens_thinking'] = {'type':'tokens','pattern':r'Thinking input: (?P<value>\d+)'}
        rule['fields']['max_input_tokens_non_thinking'] = {'type':'tokens','pattern':r'Non-thinking input: (?P<value>\d+)'}
        rule['fields']['max_input_tokens_thinking']['pattern'] = r'^Thinking input: (?P<value>\d+)'
        data = parse_rule(rule, self.text + '\nThinking input: 983616\nNon-thinking input: 991808')
        self.assertIsNone(data['values']['max_input_tokens'])
        self.assertEqual(data['values']['max_input_tokens_thinking'], 983616)
        self.assertEqual(data['values']['max_input_tokens_non_thinking'], 991808)

    def test_claude_columns_are_selected_by_model_id_not_position(self):
        rule = {'kind':'claude_table', 'url':'https://official.example', 'official_model_id':'claude-sonnet-5-5', 'scope':'API'}
        text = '\n'.join(['| Claude API ID | claude-sonnet-5-5 | claude-opus-5-5',
                          '| Context window | 1M tokens | 2M tokens',
                          '| Max output | 64K tokens | 128K tokens',
                          '| Thinking | Adaptive | Adaptive (always on)'])
        parsed = parse_rule(rule, text)
        self.assertEqual(parsed['values']['max_output_tokens'], 64000)

    def test_html_scripts_do_not_become_evidence(self):
        self.assertNotIn('forged', page_text('<html><script>forged</script><p>Model One</p></html>'))

    def test_deepseek_flash_accepts_dated_model_version(self):
        config = json.loads((Path(__file__).resolve().parents[1] / 'official_sources.json').read_text())
        rule = config['models']['deepseek/deepseek-v4.1-flash']
        text = '\n'.join([
            '| MODEL VERSION | DeepSeek-V4.1-Flash-1017 | DeepSeek-V4-Pro-0813',
            '| THINKING MODE | Supports both non-thinking and thinking (default) modes',
            '| CONTEXT LENGTH | 1M',
            '| MAX OUTPUT | MAXIMUM: 384K',
            '| Tool Calls | ✓ | ✓',
            '| Vision | ✓ | Not supported',
        ])
        parsed = parse_rule(rule, text)
        self.assertEqual(parsed['values']['context_tokens'], 1_000_000)
        self.assertEqual(parsed['values']['max_output_tokens'], 384_000)
        self.assertEqual(parsed['values']['input_modalities'], ['text', 'image'])
        self.assertTrue(parsed['values']['reasoning'])

    def test_kimi_k3_accepts_previous_generation_wording(self):
        config = json.loads((Path(__file__).resolve().parents[1] / 'official_sources.json').read_text())
        rule = config['models']['moonshotai/kimi-k3']
        text = '\n'.join([
            'Kimi K3 is Kimi’s previous-generation flagship model, with native visual understanding and a 1M-token context window.',
            'K3 always has thinking mode enabled',
            '"type": "video_url"',
        ])
        parsed = parse_rule(rule, text)
        self.assertEqual(parsed['values']['context_tokens'], 1_000_000)
        self.assertEqual(parsed['values']['input_modalities'], ['text', 'image', 'video'])
        self.assertTrue(parsed['values']['reasoning'])

    def test_glm_flash_reads_markdown_spec_cards(self):
        config = json.loads((Path(__file__).resolve().parents[1] / 'official_sources.json').read_text())
        rule = config['models']['z-ai/glm-5.3-flash']
        text = '\n'.join([
            '**Model Code**：`glm-5.3-flash`/`glm-5.3-flashx`/`glm-5.3-flashx-legal`',
            '> **Input Modality**',
            '>',
            '> Video / Image / Text / File',
            '> **Output Modality**',
            '>',
            '> Text',
            '> **Context Length**',
            '>',
            '> 1M',
            '> **Maximum Output Tokens**',
            '>',
            '> 128K',
            'Provides powerful tool-calling capabilities',
            '`thinking.type` only supports `enabled`',
        ])
        parsed = parse_rule(rule, text)
        self.assertEqual(parsed['values']['context_tokens'], 1_000_000)
        self.assertEqual(parsed['values']['max_output_tokens'], 128_000)
        self.assertEqual(parsed['values']['input_modalities'], ['text', 'image', 'video', 'file'])
        self.assertTrue(parsed['values']['tool_call'])
        self.assertTrue(parsed['values']['reasoning'])

    def test_deepseek_flash_rejects_a_different_model_line(self):
        config = json.loads((Path(__file__).resolve().parents[1] / 'official_sources.json').read_text())
        rule = config['models']['deepseek/deepseek-v4.1-flash']
        text = '| MODEL VERSION | DeepSeek-V5-Flash | DeepSeek-V4-Pro-0813'
        with self.assertRaises(ValueError):
            parse_rule(rule, text)


if __name__ == '__main__':
    unittest.main()
