import contextlib
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from typesafe_sdk import NoulAnswer, ScoreAnswer, TypeSafeError

from tidy import experiment, store
from tidy.__main__ import main
from tidy.collector import CollectResult
from test_evidence_store import NOW, sample
from test_judge import response


def score(value, confidence=0.8):
    return ScoreAnswer(score=value, confidence=confidence, legend={0: "a"}, probabilities={2: 1.0})


def by_schema(state):
    """Fake reply: the described schema sees videos with a description key and answers differently."""
    if "description" in state["videos"][0]:
        return response(relevance=score(1.9), apparent_value=score(1.5), packaging_risk=NoulAnswer(noul=0.5))
    return response(relevance=score(2.4), apparent_value=score(1.9), packaging_risk=NoulAnswer(noul=0.2))


class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = store.connect(Path(self.temp.name) / "inventory.sqlite3")
        store.save_samples(self.db, CollectResult([sample("a", "Channel a", evidence_hash="ha"),
                                                   sample("b", "Channel b", evidence_hash="hb")], {}), 6, now=NOW)
        self.client = Mock(system_one=Mock(side_effect=lambda **kw: by_schema(kw["state"])))

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def run_both(self):
        return experiment.run(self.db, self.client, ["titles-v1", "titles-desc-v1"], "x", now=NOW)

    def test_two_schemas_over_the_same_stored_samples(self):
        report = self.run_both()

        self.assertEqual(report["samples"], 2)
        self.assertEqual(self.client.system_one.call_count, 4)
        cell = report["channels"]["a"]["schemas"]["titles-desc-v1"]
        self.assertEqual(cell["relevance"], {"score": 1.9, "confidence": 0.8})
        self.assertEqual(cell["packaging_risk"], {"noul": 0.5})
        self.assertEqual(cell["usage"], {"input_tokens": 1200, "output_tokens": 10})
        self.assertGreaterEqual(cell["latency_ms"], 0)
        totals = report["schemas"]["titles-v1"]
        self.assertEqual((totals["input_tokens"], totals["output_tokens"]), (2400, 20))
        self.assertEqual((totals["calls"], totals["cache_hits"]), (2, 0))
        self.assertGreaterEqual(totals["latency_ms_max"], 0)
        self.assertGreaterEqual(report["wall_ms"], 0)

    def test_habits_reach_jev_for_the_watch_schema(self):
        experiment.run(self.db, self.client, ["titles-v2"], "x", now=NOW, habits="short explainers, Hindi or English")

        state = self.client.system_one.call_args.kwargs["state"]
        self.assertEqual(state["owner_viewing_habits"], "short explainers, Hindi or English")

    def test_repeat_run_is_all_cache_hits_and_costs_no_calls(self):
        self.run_both()
        self.client.system_one.reset_mock()

        report = self.run_both()

        self.assertEqual(self.client.system_one.call_count, 0)
        self.assertEqual({(t["calls"], t["cache_hits"]) for t in report["schemas"].values()}, {(0, 2)})
        self.assertEqual({(t["input_tokens"], t["latency_ms_sum"]) for t in report["schemas"].values()}, {(0, 0)})

    def test_disagreements_flag_at_threshold_with_exact_differences(self):
        d = self.run_both()["channels"]["a"]["disagreements"]["titles-v1|titles-desc-v1"]

        self.assertEqual(d["relevance"], {"diff": 0.5, "flagged": True})
        self.assertEqual(d["apparent_value"], {"diff": 0.4, "flagged": False})
        self.assertEqual(d["packaging_risk"], {"diff": 0.3, "flagged": True})
        self.assertEqual(d["evidence_sufficiency"], {"diff": 0.0, "flagged": False})

    def test_a_failing_sample_is_reported_not_fatal(self):
        def reply(**kw):
            if kw["state"]["channel"] == "Channel b":
                raise TypeSafeError("service down")
            return by_schema(kw["state"])
        self.client.system_one.side_effect = reply

        report = self.run_both()

        self.assertEqual(report["schemas"]["titles-v1"]["errors"], {"b": "service down"})
        self.assertEqual(report["channels"]["b"]["schemas"], {})
        self.assertIn("titles-v1|titles-desc-v1", report["channels"]["a"]["disagreements"])


class JudgeDryRunTests(unittest.TestCase):
    def test_dry_run_is_offline_needs_no_key_and_estimates_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = store.connect(Path(tmp) / "inventory.sqlite3")
            store.save_samples(db, CollectResult([sample("a", fetched=datetime.now(timezone.utc)),
                                                sample("b", "Channel b", fetched=datetime.now(timezone.utc))], {}), 6)
            db.close()
            out = io.StringIO()
            with patch.dict(os.environ, {}, clear=True), patch("typesafe_sdk.TypeSafeClient") as client, \
                    contextlib.redirect_stdout(out):
                code = main(["--data-dir", tmp, "judge", "--schemas", "titles-v1", "titles-desc-v1"])

        plan = json.loads(out.getvalue())
        client.assert_not_called()
        self.assertEqual(code, 0)
        self.assertEqual((plan["executes"], plan["samples"], plan["calls"]), (False, 2, 4))
        self.assertEqual(plan["schemas"], ["titles-v1", "titles-desc-v1"])
        self.assertGreater(plan["estimated_input_tokens"], 0)


if __name__ == "__main__":
    unittest.main()
