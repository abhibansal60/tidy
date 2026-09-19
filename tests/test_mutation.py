import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

import requests

from jev_manager import mutate, store
from jev_manager.__main__ import main
from jev_manager.youtube import APIError, UnknownOutcome, WRITE_SCOPES, YouTube, check_scopes
from test_inventory import IDENTITY, item, response


def api_with(subscriptions, delete=None, owner="owner-channel"):
    session = Mock()
    session.get.side_effect = [
        response({"sub": "google-user", "email": "owner@example.com", "email_verified": True}),
        response({"items": [{"id": owner}]}),
        response({"items": subscriptions}),
    ]
    session.delete.side_effect = delete or [Mock(status_code=204)] * 10
    return YouTube(session, 500), session


class MutationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = store.connect(Path(self.temp.name) / "inventory.sqlite3")
        store.bind_account(self.db, IDENTITY)
        store.save_inventory(self.db, IDENTITY, [
            {"id": "sub-a", "channel_id": "a", "title": "A", "subscribed_at": None},
            {"id": "sub-b", "channel_id": "b", "title": "B", "subscribed_at": None},
        ], self.db.execute("INSERT INTO sync_runs(started_at,status) VALUES ('t','running')").lastrowid, 3)

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def status(self, sub):
        return self.db.execute("SELECT status FROM unsubscribes WHERE subscription_id=?", (sub,)).fetchone()[0]

    def test_dry_run_is_offline_and_only_lists_approved(self):
        mutate.approve(self.db, ["a"], "test proposal")
        out = mutate.unsubscribe(self.db, None, None, False)
        self.assertTrue(out["dry_run"])
        self.assertEqual([p["title"] for p in out["pending"]], ["A"])
        self.assertEqual(self.status("sub-a"), "approved")

    def test_cannot_approve_unknown_or_inactive_channel(self):
        with self.assertRaises(ValueError):
            mutate.approve(self.db, ["zzz"], "x")

    def test_execute_deletes_only_approved_and_is_idempotent(self):
        mutate.approve(self.db, ["a"], "test proposal")
        api, session = api_with([item("a"), item("b")])
        out = mutate.unsubscribe(self.db, api, "owner@example.com", True)
        self.assertEqual(out["results"], [("A", "deleted")])
        self.assertEqual(session.delete.call_count, 1)
        self.assertEqual(session.delete.call_args.kwargs["params"], {"id": "sub-a"})
        self.assertEqual(self.status("sub-a"), "done")
        active = [r[0] for r in self.db.execute("SELECT channel_id FROM subscriptions WHERE active=1")]
        self.assertEqual(active, ["b"])
        again = mutate.unsubscribe(self.db, None, None, True)  # nothing pending: no network needed
        self.assertEqual(again["pending"], [])

    def test_already_absent_is_reconciled_without_delete(self):
        mutate.approve(self.db, ["a"], "x")
        api, session = api_with([item("b")])
        out = mutate.unsubscribe(self.db, api, "owner@example.com", True)
        self.assertEqual(out["results"], [("A", "already_absent")])
        session.delete.assert_not_called()

    def test_resubscribed_under_new_id_is_not_deleted(self):
        mutate.approve(self.db, ["a"], "x")
        api, session = api_with([item("a", "new-id")])
        out = mutate.unsubscribe(self.db, api, "owner@example.com", True)
        self.assertEqual(out["results"], [("A", "skipped_resubscribed")])
        session.delete.assert_not_called()
        self.assertEqual(self.status("sub-a"), "approved")

    def test_unknown_outcome_stops_then_reconciles_before_retry(self):
        mutate.approve(self.db, ["a", "b"], "x")
        api, session = api_with([item("a"), item("b")], delete=[requests.ConnectionError()])
        with self.assertRaises(UnknownOutcome):
            mutate.unsubscribe(self.db, api, "owner@example.com", True)
        self.assertEqual(session.delete.call_count, 1)  # stopped, did not continue to b
        self.assertEqual(self.status("sub-a"), "unknown")
        api, session = api_with([item("b")])  # the ambiguous delete had actually succeeded
        out = mutate.unsubscribe(self.db, api, "owner@example.com", True)
        self.assertEqual(dict(out["results"])["A"], "already_absent")
        self.assertEqual(self.status("sub-a"), "done")

    def test_http_404_counts_as_absent_and_403_stays_approved(self):
        mutate.approve(self.db, ["a"], "x")
        api, _ = api_with([item("a")], delete=[Mock(status_code=403)])
        with self.assertRaises(APIError):
            mutate.unsubscribe(self.db, api, "owner@example.com", True)
        self.assertEqual(self.status("sub-a"), "approved")
        api, _ = api_with([item("a")], delete=[Mock(status_code=404)])
        self.assertEqual(mutate.unsubscribe(self.db, api, "owner@example.com", True)["results"], [("A", "absent")])

    def test_wrong_account_refuses_before_any_delete(self):
        mutate.approve(self.db, ["a"], "x")
        api, session = api_with([item("a")], owner="another-channel")
        with self.assertRaises(ValueError):
            mutate.unsubscribe(self.db, api, "owner@example.com", True)
        session.delete.assert_not_called()

    def test_budget_blocks_delete(self):
        mutate.approve(self.db, ["a"], "x")
        api, session = api_with([item("a")])
        api.max_units = 10
        with self.assertRaisesRegex(APIError, "budget"):
            mutate.unsubscribe(self.db, api, "owner@example.com", True)
        session.delete.assert_not_called()

    def test_audit_trail_records_events(self):
        mutate.approve(self.db, ["a"], "x")
        api, _ = api_with([item("a")])
        mutate.unsubscribe(self.db, api, "owner@example.com", True)
        events = [r[0] for r in self.db.execute("SELECT event FROM audit_events ORDER BY id")]
        self.assertEqual(events, ["approved", "done"])

    def test_write_scope_is_separate_from_read_scope(self):
        check_scopes(WRITE_SCOPES, write=True)
        with self.assertRaises(APIError):
            check_scopes(WRITE_SCOPES)  # a write grant is rejected on the read path
        with self.assertRaises(APIError):
            check_scopes(["https://www.googleapis.com/auth/youtube.readonly", "openid"], write=True)

    def test_cli_dry_run_makes_no_network_calls(self):
        self.db.close()
        with contextlib.redirect_stdout(io.StringIO()):
            code = main(["--data-dir", self.temp.name, "unsubscribe"])
        self.assertEqual(code, 0)
        self.db = store.connect(Path(self.temp.name) / "inventory.sqlite3")


if __name__ == "__main__":
    unittest.main()
