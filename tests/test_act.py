import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

import requests

from tidy import mutate, store
from tidy.__main__ import main
from tidy.proposal import Proposal
from tidy.youtube import APIError, UnknownOutcome, YouTube
from test_inventory import IDENTITY, item, response

TWO = ["value low (0.2)", "relevance low (0.1)"]


def reply(status, reason=None, sub_id="new-sub"):
    r = Mock(status_code=status, headers={})
    r.json.return_value = ({"id": sub_id} if status == 200 else
                           {"error": {"errors": [{"reason": reason}]}})
    return r


def api_with(subscriptions, post=None, delete=None, owner="owner-channel", max_units=500):
    session = Mock()
    session.get.side_effect = [
        response({"sub": "google-user", "email": "owner@example.com", "email_verified": True}),
        response({"items": [{"id": owner}]}),
        response({"items": subscriptions}),
    ]
    session.post.side_effect = post or [reply(200)] * 10
    session.delete.side_effect = delete or [Mock(status_code=204)] * 10
    return YouTube(session, max_units), session


def prop(channel, action, signals=TWO):
    return Proposal(channel_id=channel, action=action, signals=list(signals))


OPEN = {"UNSUBSCRIBE": True, "SUBSCRIBE": True}
CAPS = {"unsubscribe": 5, "subscribe": 3}


class SubscribeTests(unittest.TestCase):
    def test_subscribe_posts_once_and_costs_50(self):
        api, session = api_with([], post=[reply(200, sub_id="s1")])
        self.assertEqual(api.subscribe("chan"), ("subscribed", "s1"))
        self.assertEqual(api.units, 50)
        self.assertEqual(session.post.call_args.kwargs["json"],
                         {"snippet": {"resourceId": {"kind": "youtube#channel", "channelId": "chan"}}})

    def test_duplicate_is_idempotent_success(self):
        api, _ = api_with([], post=[reply(400, "subscriptionDuplicate")])
        self.assertEqual(api.subscribe("chan"), ("exists", None))

    def test_ambiguous_failures_are_unknown_and_not_retried(self):
        for bad in (requests.ConnectionError(), reply(500), reply(429)):
            api, session = api_with([], post=[bad])
            with self.assertRaises(UnknownOutcome):
                api.subscribe("chan")
            self.assertEqual(session.post.call_count, 1)

    def test_other_client_errors_and_budget(self):
        api, _ = api_with([], post=[reply(403, "forbidden")])
        with self.assertRaises(APIError) as caught:
            api.subscribe("chan")
        self.assertNotIsInstance(caught.exception, UnknownOutcome)
        api, session = api_with([], max_units=49)
        with self.assertRaisesRegex(APIError, "budget"):
            api.subscribe("chan")
        session.post.assert_not_called()


class ActTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = store.connect(Path(self.temp.name) / "inventory.sqlite3")
        store.bind_account(self.db, IDENTITY)
        self.load([c for c in "abcdefghij"])

    def load(self, channels):
        store.save_inventory(self.db, IDENTITY, [
            {"id": "sub-" + c, "channel_id": c, "title": c.upper(), "subscribed_at": None} for c in channels],
            self.db.execute("INSERT INTO sync_runs(started_at,status) VALUES ('t','running')").lastrowid, 3)

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def act(self, proposals, api=None, gates=OPEN, caps=CAPS, execute=False, **kw):
        return mutate.act(self.db, api, proposals, gates, caps, "owner@example.com", execute, **kw)

    def outcomes(self, out):
        return [(a["action"], a["channel_id"], a["result"]) for a in out["actions"]]

    def test_dry_run_is_offline_and_reports_plan(self):
        out = self.act([prop("a", "UNSUBSCRIBE"), prop("z", "SUBSCRIBE"), prop("b", "KEEP")])
        self.assertTrue(out["dry_run"])
        self.assertEqual(self.outcomes(out), [("UNSUBSCRIBE", "a", "would"), ("SUBSCRIBE", "z", "would")])
        self.assertEqual(self.db.execute("SELECT count(*) FROM auto_actions").fetchone()[0], 0)

    def test_closed_gate_never_acts(self):
        out = self.act([prop("a", "UNSUBSCRIBE"), prop("z", "SUBSCRIBE")],
                       gates={"UNSUBSCRIBE": False, "SUBSCRIBE": True})
        self.assertEqual(self.outcomes(out), [("UNSUBSCRIBE", "a", "skipped: gate closed"),
                                              ("SUBSCRIBE", "z", "would")])

    def test_caps_apply_per_action_type(self):
        props = [prop(c, "UNSUBSCRIBE") for c in "abc"] + [prop(c, "SUBSCRIBE") for c in "xyz"]
        out = self.act(props, caps={"unsubscribe": 1, "subscribe": 2})
        self.assertEqual(self.outcomes(out), [
            ("UNSUBSCRIBE", "a", "would"), ("UNSUBSCRIBE", "b", "skipped: cap"),
            ("UNSUBSCRIBE", "c", "skipped: cap"), ("SUBSCRIBE", "x", "would"),
            ("SUBSCRIBE", "y", "would"), ("SUBSCRIBE", "z", "skipped: cap")])

    def test_single_signal_and_wrong_state_are_skipped(self):
        out = self.act([prop("a", "UNSUBSCRIBE", ["value low"]), prop("zz", "UNSUBSCRIBE"),
                        prop("b", "SUBSCRIBE")])
        self.assertEqual(self.outcomes(out), [
            ("UNSUBSCRIBE", "a", "skipped: fewer than two signals"),
            ("UNSUBSCRIBE", "zz", "skipped: not subscribed"),
            ("SUBSCRIBE", "b", "skipped: already subscribed")])

    def test_anomaly_threshold_is_max_of_three_caps_and_a_fifth_of_subscriptions(self):
        caps = {"unsubscribe": 1, "subscribe": 1}  # 10 subs: max(3, 2) = 3
        ok = self.act([prop(c, "UNSUBSCRIBE") for c in "abc"], caps=caps)
        self.assertIsNone(ok["aborted"])
        bad = self.act([prop(c, "UNSUBSCRIBE") for c in "abcd"], caps=caps)
        self.assertIn("4 unsubscribe proposals", bad["aborted"])
        self.assertEqual(bad["actions"], [])
        self.load([f"c{i}" for i in range(50)])  # 50 subs: max(3, 10) = 10
        ten = self.act([prop(f"c{i}", "UNSUBSCRIBE") for i in range(10)], caps=caps)
        self.assertIsNone(ten["aborted"])
        eleven = self.act([prop(f"c{i}", "UNSUBSCRIBE") for i in range(11)], caps=caps)
        self.assertIsNotNone(eleven["aborted"])

    def test_anomaly_abort_on_execute_makes_no_calls(self):
        caps = {"unsubscribe": 1, "subscribe": 1}
        api, session = api_with([item(c) for c in "abcdefghij"])
        out = self.act([prop(c, "UNSUBSCRIBE") for c in "abcd"] + [prop("z", "SUBSCRIBE")],
                       api, caps=caps, execute=True)
        self.assertIsNotNone(out["aborted"])
        session.delete.assert_not_called()
        session.post.assert_not_called()

    def test_execute_acts_audits_and_records_trial_and_reversal(self):
        live = [item(c) for c in "abcdefghij"]
        api, session = api_with(live, post=[reply(200, sub_id="new-z")])
        out = self.act([prop("a", "UNSUBSCRIBE"), prop("z", "SUBSCRIBE")], api, execute=True, trial_days=30)
        self.assertEqual(self.outcomes(out), [("UNSUBSCRIBE", "a", "deleted"), ("SUBSCRIBE", "z", "subscribed")])
        self.assertEqual(session.delete.call_args.kwargs["params"], {"id": "sub-a"})
        events = [r[0] for r in self.db.execute("SELECT event FROM audit_events ORDER BY id")]
        self.assertEqual(events, ["auto_unsubscribe_done", "auto_subscribe_done"])
        row = self.db.execute("SELECT * FROM trials").fetchone()
        self.assertEqual((row["channel_id"], row["subscription_id"]), ("z", "new-z"))
        self.assertEqual(datetime.fromisoformat(row["trial_ends_at"]) - datetime.fromisoformat(row["subscribed_at"]),
                         timedelta(days=30))
        undo = self.db.execute("SELECT subscription_id, channel_id, title, at FROM auto_actions "
                               "WHERE action='UNSUBSCRIBE'").fetchone()
        self.assertEqual(tuple(undo)[:3], ("sub-a", "a", "A"))
        self.assertTrue(undo["at"])
        self.assertEqual(self.db.execute("SELECT active FROM subscriptions WHERE id='sub-a'").fetchone()[0], 0)

    def test_execute_rechecks_live_list(self):
        api, session = api_with([item("b"), item("z")])  # a already gone, z already subscribed
        out = self.act([prop("a", "UNSUBSCRIBE"), prop("z", "SUBSCRIBE")], api, execute=True)
        self.assertEqual(self.outcomes(out), [("UNSUBSCRIBE", "a", "skipped: not subscribed"),
                                              ("SUBSCRIBE", "z", "skipped: already subscribed")])
        session.delete.assert_not_called()
        session.post.assert_not_called()

    def test_wrong_account_refuses_before_any_action(self):
        api, session = api_with([item("a")], owner="another")
        with self.assertRaises(ValueError):
            self.act([prop("a", "UNSUBSCRIBE")], api, execute=True)
        session.delete.assert_not_called()

    def test_unknown_outcome_stops_then_reconciles_without_retry(self):
        api, session = api_with([item("a"), item("b")], post=[requests.ConnectionError()])
        with self.assertRaises(UnknownOutcome):
            self.act([prop("z", "SUBSCRIBE"), prop("a", "UNSUBSCRIBE")], api, execute=True)
        session.delete.assert_not_called()  # stopped after the ambiguous action
        self.assertEqual(self.db.execute("SELECT status FROM auto_actions").fetchone()[0], "unknown")
        self.assertEqual(self.db.execute("SELECT count(*) FROM trials").fetchone()[0], 0)
        api, session = api_with([item("a"), item("b"), item("z", "real-z")])  # it had succeeded
        self.act([], api, execute=True)
        session.post.assert_not_called()
        self.assertEqual(self.db.execute("SELECT status FROM auto_actions").fetchone()[0], "done")
        self.assertEqual(self.db.execute("SELECT subscription_id FROM trials WHERE channel_id='z'").fetchone()[0],
                         "real-z")

    def test_unknown_unsubscribe_still_subscribed_is_marked_failed(self):
        api, _ = api_with([item("a")], delete=[Mock(status_code=503)])
        with self.assertRaises(UnknownOutcome):
            self.act([prop("a", "UNSUBSCRIBE")], api, execute=True)
        api, session = api_with([item("a")])
        self.act([], api, execute=True)
        session.delete.assert_not_called()
        self.assertEqual(self.db.execute("SELECT status FROM auto_actions").fetchone()[0], "failed")

    def test_trials_due_lists_only_ended_trials(self):
        api, _ = api_with([item("a")], post=[reply(200, sub_id="s")])
        self.act([prop("z", "SUBSCRIBE")], api, execute=True, trial_days=30)
        soon = datetime.now(timezone.utc) + timedelta(days=29)
        later = datetime.now(timezone.utc) + timedelta(days=31)
        self.assertEqual(mutate.trials_due(self.db, soon), [])
        self.assertEqual([t["channel_id"] for t in mutate.trials_due(self.db, later)], ["z"])

    def test_resubscribe_restores_auto_unsubscribed_channel(self):
        api, _ = api_with([item("a")])
        self.act([prop("a", "UNSUBSCRIBE")], api, execute=True)
        dry = mutate.resubscribe(self.db, None, ["a"], False)
        self.assertEqual([r["title"] for r in dry["would"]], ["A"])
        api, session = api_with([item("b")], post=[reply(200, sub_id="back")])
        out = mutate.resubscribe(self.db, api, ["a"], True, "owner@example.com")
        self.assertEqual(out["results"], [("a", "subscribed")])
        self.assertEqual(session.post.call_args.kwargs["json"]["snippet"]["resourceId"]["channelId"], "a")
        self.assertEqual(self.db.execute("SELECT status FROM auto_actions WHERE action='UNSUBSCRIBE'").fetchone()[0],
                         "restored")
        with self.assertRaises(ValueError):
            mutate.resubscribe(self.db, None, ["a"], False)  # nothing left to restore
        with self.assertRaises(ValueError):
            mutate.resubscribe(self.db, None, ["never-auto-unsubscribed"], False)

    def test_cli_dry_run_reads_proposals_file_offline(self):
        path = Path(self.temp.name) / "p.json"
        path.write_text(json.dumps([{"channel_id": "a", "action": "UNSUBSCRIBE", "signals": TWO}]))
        self.db.close()
        args = ["--data-dir", self.temp.name, "act", "--proposals", str(path)]
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(args + ["--gate-unsubscribe"]), 0)
            self.assertEqual(main(args), 0)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["--data-dir", self.temp.name, "resubscribe", "a"]), 1)  # nothing to restore
        first, second = out.getvalue().split("\n}\n")[:2]
        self.assertIn('"would"', first)
        self.assertIn("gate closed", second)
        self.db = store.connect(Path(self.temp.name) / "inventory.sqlite3")


if __name__ == "__main__":
    unittest.main()
