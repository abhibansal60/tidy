import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from evals import codex_baseline


ANSWERS = {"relevance": 3, "apparent_value": 2, "packaging_risk": 0.1, "evidence_sufficiency": 0.9}


class CodexBaselineTests(unittest.TestCase):
    def test_parse_jsonl_message_and_usage(self):
        output = "\n".join([
            json.dumps({"type": "turn.started"}),
            json.dumps({"type": "item.completed", "item": {"type": "agent_message", "content": [{"type": "output_text", "text": json.dumps(ANSWERS)}]}}),
            json.dumps({"type": "turn.completed", "usage": {"input_tokens": 12, "cached_input_tokens": 3, "output_tokens": 8}}),
        ])
        answers, tokens = codex_baseline.parse_events(output)
        self.assertEqual(answers, ANSWERS)
        self.assertEqual(tokens, {"input_tokens": 12, "cached_input_tokens": 3, "output_tokens": 8})

    def test_fake_process_produces_expected_channel_shape(self):
        events = "\n".join([
            json.dumps({"type": "item.completed", "item": {"type": "agent_message", "content": [{"type": "output_text", "text": json.dumps(ANSWERS)}]}}),
            json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1, "cached_input_tokens": 0, "output_tokens": 2}}),
        ])
        fake = Mock(return_value=Mock(returncode=0, stdout=events, stderr=""))
        result = codex_baseline.ask("gpt-test", {"channel": "synthetic", "videos": []}, run=fake, schema_path="/tmp/schema.json")
        self.assertEqual(result["answers"], ANSWERS)
        self.assertEqual(result["tokens"]["output_tokens"], 2)
        command = fake.call_args.args[0]
        self.assertIn("--sandbox", command)
        self.assertIn("read-only", command)
        self.assertIn("--ephemeral", command)
        self.assertIsNone(result["cost_usd"])

    def test_failed_process_is_safe(self):
        fake = Mock(return_value=Mock(returncode=1, stdout="private provider detail", stderr="secret"))
        result = codex_baseline.ask("gpt-test", {}, run=fake, schema_path="/tmp/schema.json")
        self.assertEqual(result["error"], "codex process failed")
        self.assertNotIn("secret", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
