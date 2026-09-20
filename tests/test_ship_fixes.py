import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

from tidy import experiment, mutate, profile, store
from tidy.__main__ import main, run_act
from tidy.proposal import Proposal

NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)


class RetentionTests(unittest.TestCase):
    def test_purge_blanks_old_titles_in_actions_and_approvals(self):
        with tempfile.TemporaryDirectory() as d:
            db = store.connect(Path(d) / "inventory.sqlite3")
            old, new = (NOW - timedelta(days=40)).isoformat(), (NOW - timedelta(days=5)).isoformat()
            with db:
                db.execute("INSERT INTO auto_actions(at,action,channel_id,title,status) VALUES (?,?,?,?,?)", (old, "UNSUBSCRIBE", "a", "Old Title", "done"))
                db.execute("INSERT INTO auto_actions(at,action,channel_id,title,status) VALUES (?,?,?,?,?)", (new, "UNSUBSCRIBE", "b", "New Title", "done"))
                db.execute("INSERT INTO unsubscribes VALUES ('s1','a','Old Title','acct',?,NULL,'done',?,NULL)", (old, old))
                db.execute("INSERT INTO unsubscribes VALUES ('s2','b','New Title','acct',?,NULL,'done',?,NULL)", (new, new))

            store.purge(db, NOW)

            self.assertEqual([r[0] for r in db.execute("SELECT title FROM auto_actions ORDER BY channel_id")], [None, "New Title"])
            self.assertEqual([r[0] for r in db.execute("SELECT title FROM unsubscribes ORDER BY subscription_id")], ["(expired)", "New Title"])
            db.close()

    def test_purge_command_reports_what_it_removed(self):
        with tempfile.TemporaryDirectory() as d:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(main(["--data-dir", d, "purge"]), 0)
            self.assertEqual(json.loads(out.getvalue()), {"purged_evidence_samples": 0})


class KeyLookupTests(unittest.TestCase):
    def test_typesafe_key_is_read_from_a_dotenv_in_the_working_directory(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TYPESAFE_API_KEY", None)
            (Path(d) / ".env").write_text("TYPESAFE_API_KEY='abc123'\n")
            cwd = os.getcwd()
            os.chdir(d)
            try:
                with patch("typesafe_sdk.TypeSafeClient") as client:
                    experiment.typesafe_client()
            finally:
                os.chdir(cwd)
            client.assert_called_once_with(api_key="abc123")


class JudgeInterestsTests(unittest.TestCase):
    def test_judge_defaults_to_the_profile_interests(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "profile.json").write_text(json.dumps({"interests": "woodworking and jazz"}))
            with patch.object(experiment, "plan", return_value={}) as plan, contextlib.redirect_stdout(io.StringIO()):
                main(["--data-dir", d, "judge", "--schemas", "titles-v1"])
            self.assertEqual(plan.call_args.args[2], "woodworking and jazz")


class ProposeJsonTests(unittest.TestCase):
    def test_propose_json_writes_the_list_that_act_reads(self):
        with tempfile.TemporaryDirectory() as d:
            path, out = Path(d) / "proposals.json", io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(main(["--data-dir", d, "propose", "--json", str(path)]), 0)

            self.assertEqual(json.loads(path.read_text()), [])
            self.assertEqual(json.loads(out.getvalue()), {"json": str(path), "channels": 0})
            self.assertEqual([Proposal(**p) for p in json.loads(path.read_text())], [])


class ActSafetyTests(unittest.TestCase):
    def test_duplicate_proposals_never_mutate_twice(self):
        props = [Proposal("a", "UNSUBSCRIBE", ["x", "y"]), Proposal("a", "UNSUBSCRIBE", ["x", "y"])]
        actions, _ = mutate._plan(props, {"UNSUBSCRIBE": True}, {"unsubscribe": 5}, {"a"}, 50)
        self.assertEqual([a["result"] for a in actions], ["would", "skipped: duplicate"])

    def test_execute_refuses_a_closed_calibration_gate_unless_overridden(self):
        with tempfile.TemporaryDirectory() as d:
            db = store.connect(Path(d) / "inventory.sqlite3")
            path = Path(d) / "p.json"
            path.write_text("[]")
            args = SimpleNamespace(command="act", proposals=path, gate_unsubscribe=True, gate_subscribe=False,
                                   cap_unsubscribe=None, cap_subscribe=None, execute=True, override_gate=False)
            config = profile.load(Path(d) / "none.json")
            with self.assertRaisesRegex(ValueError, "Calibration gate closed"):
                run_act(db, Mock(), "me@example.com", args, config)
            db.close()


if __name__ == "__main__":
    unittest.main()
