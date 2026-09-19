from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from tidy import escalate, profile, store
from tidy.collector import CollectResult
from tidy.judge import interests_key
from test_evidence_store import NOW, sample
from test_policy import judgment


class EscalateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = store.connect(Path(self.temp.name) / "inventory.sqlite3")
        self.profile = {**profile.load(Path("/nonexistent")), "schema_id": "titles-v1"}
        self.key = interests_key(self.profile["interests"], self.profile["viewing_habits"])
        for cid, value in [("low", 0.2), ("mid", 0.9), ("high", 2.4)]:
            s = sample(channel=cid, title="Channel " + cid, evidence_hash="h" + cid)
            store.save_samples(self.db, CollectResult([s], {}), 1, now=NOW)
            j = judgment(val=value, evidence_hash="h" + cid)
            j.channel_id = cid
            store.put_judgment(self.db, j, self.key, s.expires_at)

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_only_channels_below_the_low_quality_threshold_are_flagged_and_estimated(self):
        plan = escalate.plan(self.db, self.profile, now=NOW)

        self.assertEqual(plan, {"flagged": ["low"], "calls": 1, "executes": False})

    def test_run_asks_once_for_flagged_channels_and_stores_the_second_opinion(self):
        ask = Mock(return_value={"answers": {"relevance": 1, "apparent_value": 0.3, "packaging_risk": 0.5,
                                             "evidence_sufficiency": 0.4}})

        first = escalate.run(self.db, self.profile, ask, "opus-x", now=NOW)
        again = escalate.run(self.db, self.profile, ask, "opus-x", now=NOW)

        self.assertEqual((first["flagged"], first["stored"]), (1, 1))
        self.assertEqual(ask.call_count, 1)
        self.assertEqual(again["stored"], 0)
        stored = store.get_second_opinion(self.db, "low", "hlow", NOW)
        self.assertEqual(stored["apparent_value"], 0.3)
        self.assertEqual(ask.call_args.args[0], "opus-x")
        self.assertEqual(ask.call_args.args[1]["channel"], "Channel low")

    def test_a_failed_ask_is_reported_and_nothing_is_stored(self):
        ask = Mock(return_value={"error": "timeout", "wall_ms": 5})

        result = escalate.run(self.db, self.profile, ask, "opus-x", now=NOW)

        self.assertEqual((result["stored"], result["errors"]), (0, {"low": "timeout"}))
        self.assertIsNone(store.get_second_opinion(self.db, "low", "hlow", NOW))

    def test_escalate_command_is_a_dry_run_by_default_and_needs_no_claude(self):
        import contextlib, io, json
        from unittest.mock import patch
        from tidy.__main__ import main
        (Path(self.temp.name) / "profile.json").write_text(json.dumps({"schema_id": "titles-v1"}))
        out = io.StringIO()
        with patch("tidy.escalate.ask", side_effect=AssertionError("must not call Claude")), \
                contextlib.redirect_stdout(out):
            code = main(["--data-dir", self.temp.name, "escalate"])

        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())["executes"], False)


if __name__ == "__main__":
    unittest.main()
