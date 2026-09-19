import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from types import SimpleNamespace

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

    def test_resume_only_reasks_failed_channels(self):
        samples = [SimpleNamespace(channel_id="a"), SimpleNamespace(channel_id="b")]
        existing = {"model": "gpt-test", "effort": None, "workers": 6,
                    "wall_ms": 1, "channels": {"a": {"answers": ANSWERS},
                    "b": {"error": "quota", "wall_ms": 2}}}
        asked = []
        def fake_ask(model, state, effort):
            asked.append(state["id"])
            return {"answers": ANSWERS, "wall_ms": 3, "tokens": {}, "cost_usd": None}
        with unittest.mock.patch.object(codex_baseline.store, "connect"), \
             unittest.mock.patch.object(codex_baseline, "eval_samples", return_value=samples), \
             unittest.mock.patch.object(codex_baseline.judge, "_state", side_effect=lambda sample, *_: {"id": sample.channel_id}):
            report = codex_baseline.run_eval("gpt-test", None, Path("."), ask_fn=fake_ask, existing=existing)
        self.assertEqual(asked, ["b"])
        self.assertEqual(list(report["channels"]), ["a", "b"])


if __name__ == "__main__":
    unittest.main()


class EvalSamplesTests(unittest.TestCase):
    def test_only_the_original_experiment_channels_are_evaluated(self):
        from datetime import datetime, timezone
        from tidy import store
        from tidy.collector import CollectResult
        from test_evidence_store import sample

        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as d:
            db = store.connect(Path(d) / "inventory.sqlite3")
            store.save_samples(db, CollectResult([sample(channel=c, evidence_hash="h" + c, fetched=now) for c in ("a", "b", "cand")], {}), 1, now)
            (Path(d) / "experiment_2.json").write_text(json.dumps({"channels": {"a": {}, "b": {}}}))

            from evals.claude_baseline import eval_samples
            self.assertEqual([s.channel_id for s in eval_samples(db, Path(d))], ["a", "b"])
            self.assertEqual([s.channel_id for s in eval_samples(db, Path(d), limit=1)], ["a"])
            db.close()
