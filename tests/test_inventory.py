import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from jev_manager import store
from jev_manager.__main__ import sync
from jev_manager.youtube import APIError, READ_SCOPE, SCOPES, YouTube, authorize, check_scopes


IDENTITY = {"google_sub": "google-user", "email": "owner@example.com", "youtube_channel_id": "owner-channel"}


def response(payload, status=200):
    result = Mock(status_code=status, headers={})
    result.json.return_value = payload
    return result


def item(channel, subscription=None):
    return {"id": subscription or "sub-" + channel,
            "snippet": {"resourceId": {"channelId": channel}, "title": "Channel " + channel,
                        "publishedAt": "2026-01-01T00:00:00Z"}}


def session_with(*pages, email="owner@example.com", owner="owner-channel"):
    session = Mock()
    session.get.side_effect = [
        response({"sub": "google-user", "email": email, "email_verified": True}),
        response({"items": [{"id": owner}]}), *pages,
    ]
    return session


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = store.connect(self.root / "inventory.sqlite3")

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def run_sync(self, *pages, **kwargs):
        session = session_with(*pages, **kwargs)
        result = sync(self.db, YouTube(session), "owner@example.com")
        session.post.assert_not_called()
        session.delete.assert_not_called()
        session.put.assert_not_called()
        return result

    def active(self):
        return [r[0] for r in self.db.execute("SELECT channel_id FROM subscriptions WHERE active=1 ORDER BY channel_id")]

    def test_complete_paginated_import_repeat_and_reconciliation(self):
        first = response({"items": [item("a")], "nextPageToken": "page2"})
        second = response({"items": [item("b")]})
        session = session_with(first, second)
        result = sync(self.db, YouTube(session), "owner@example.com")
        self.assertEqual(result["estimated_quota_units"], 3)
        self.assertEqual(session.get.call_args.kwargs["params"]["pageToken"], "page2")
        self.assertEqual(self.active(), ["a", "b"])
        self.run_sync(first, second)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0], 2)
        self.run_sync(response({"items": [item("b", "replacement-id")]}))
        self.assertEqual(self.active(), ["b"])
        self.assertEqual(self.db.execute("SELECT id FROM subscriptions WHERE channel_id='b'").fetchone()[0], "replacement-id")

    def test_failure_after_first_page_keeps_previous_inventory(self):
        self.run_sync(response({"items": [item("a"), item("b")]}))
        with self.assertRaises(APIError):
            self.run_sync(response({"items": [item("c")], "nextPageToken": "p2"}), response({}, 403))
        self.assertEqual(self.active(), ["a", "b"])
        report = store.report(self.db)
        self.assertEqual(report["last_attempt"]["status"], "failed")
        self.assertEqual(report["active_subscriptions"], 2)

    def test_wrong_google_account_never_fetches_subscriptions(self):
        session = session_with(email="other@example.com")
        with self.assertRaises(APIError):
            sync(self.db, YouTube(session), "owner@example.com")
        self.assertEqual(session.get.call_count, 1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM account").fetchone()[0], 0)

    def test_different_youtube_identity_rejected(self):
        store.bind_account(self.db, IDENTITY)
        session = session_with(owner="another-channel")
        with self.assertRaises(ValueError):
            sync(self.db, YouTube(session), "owner@example.com")
        self.assertEqual(session.get.call_count, 2)

    def test_empty_completed_inventory_is_valid(self):
        self.run_sync(response({"items": [item("a")]}))
        self.run_sync(response({"items": []}))
        self.assertEqual(self.active(), [])
        self.assertEqual(store.report(self.db)["active_subscriptions"], 0)

    def test_malformed_duplicate_and_looped_pages_fail_closed(self):
        cases = [
            [response({})],
            [response({"items": [{"id": "missing-snippet"}]})],
            [response({"items": [item("a"), item("a")]})],
            [response({"items": [], "nextPageToken": 0})],
            [response({"items": [item("a")], "nextPageToken": "same"}),
             response({"items": [], "nextPageToken": "same"})],
        ]
        for pages in cases:
            with self.subTest(pages=len(pages)), self.assertRaises(APIError):
                self.run_sync(*pages)
            self.assertEqual(self.active(), [])

    def test_budget_includes_identity_and_page_requests(self):
        session = session_with(response({"items": [item("a")], "nextPageToken": "p2"}))
        with self.assertRaisesRegex(APIError, "budget"):
            sync(self.db, YouTube(session, max_units=2), "owner@example.com")
        self.assertEqual(session.get.call_count, 3)  # userinfo does not spend YouTube units
        self.assertEqual(self.active(), [])

    @patch("jev_manager.youtube.time.sleep")
    def test_retry_counts_units_and_uses_only_get(self, sleep):
        session = Mock()
        session.get.side_effect = [response({}, 503), response({"items": []})]
        api = YouTube(session)
        self.assertEqual(api.subscriptions(), [])
        self.assertEqual(api.units, 2)
        sleep.assert_called_once_with(1)
        session.delete.assert_not_called()
        with self.assertRaises(ValueError):
            api.get("subscriptions/delete")

    def test_legacy_import_is_idempotent_and_not_live(self):
        csv = self.root / "subscriptions.csv"
        results = self.root / "results.json"
        csv.write_text("Channel ID,Channel title\na,Example\nb,Unavailable\n")
        original = [{"id": "a", "tier": "good", "titles": ["A title"]}, {"id": "b", "error": "no videos"}]
        results.write_text(json.dumps(original))
        self.assertFalse(store.import_legacy(self.db, csv, results)["already_imported"])
        self.assertTrue(store.import_legacy(self.db, csv, results)["already_imported"])
        report = store.report(self.db)
        self.assertEqual(report["legacy_channels"], 2)
        self.assertIsNone(report["active_subscriptions"])
        self.assertIsNone(report["absent_since_legacy"])
        saved = self.db.execute("SELECT result_json FROM legacy_channels WHERE channel_id='b'").fetchone()[0]
        self.assertEqual(json.loads(saved), original[1])
        self.run_sync(response({"items": [item("a"), item("c")]}))
        self.assertEqual(store.report(self.db)["absent_since_legacy"], ["b"])
        self.assertEqual(store.report(self.db)["new_since_legacy"], ["c"])

    def test_bad_legacy_import_leaves_no_partial_rows(self):
        csv = self.root / "subscriptions.csv"
        results = self.root / "results.json"
        csv.write_text("Channel ID,Channel title\na,Example\na,Duplicate\n")
        results.write_text("[]")
        with self.assertRaises(ValueError):
            store.import_legacy(self.db, csv, results)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM legacy_imports").fetchone()[0], 0)

    def test_stale_api_metadata_purged_on_open_and_report_not_current(self):
        self.run_sync(response({"items": [item("a")]}))
        with self.db:
            self.db.execute("UPDATE subscriptions SET last_seen='2000-01-01T00:00:00+00:00'")
            self.db.execute("UPDATE sync_runs SET finished_at='2000-01-01T00:00:00+00:00'")
        self.db.close()
        self.db = store.connect(self.root / "inventory.sqlite3")
        self.assertEqual(self.active(), [])
        self.assertEqual(store.report(self.db)["live_inventory"], "missing_or_expired")
        self.assertIsNone(store.report(self.db)["active_subscriptions"])

    def test_scopes_reject_write_grants(self):
        check_scopes(SCOPES)
        with self.assertRaises(APIError):
            check_scopes(SCOPES + ["https://www.googleapis.com/auth/youtube"])
        with self.assertRaises(APIError):
            check_scopes(["openid"])

    def test_credentials_written_atomically_with_private_permissions(self):
        path = self.root / "private" / "token.json"
        store.private_json(path, {"refresh_token": "fake"})
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
        store.private_json(path, {"refresh_token": "replacement"})
        self.assertEqual(json.loads(path.read_text())["refresh_token"], "replacement")

    @patch("jev_manager.youtube.InstalledAppFlow")
    def test_oauth_uses_loopback_pkce_and_read_only_scopes(self, flow_class):
        path = self.root / "client.json"
        config = {"installed": {"auth_uri": "https://accounts.google.com/o/oauth2/auth",
                                "token_uri": "https://oauth2.googleapis.com/token"}}
        path.write_text(json.dumps(config))
        credentials = Mock(granted_scopes=SCOPES, refresh_token="fake")
        flow_class.from_client_config.return_value.run_local_server.return_value = credentials
        self.assertIs(authorize(path, "owner@example.com", False), credentials)
        flow_class.from_client_config.assert_called_once_with(config, SCOPES, autogenerate_code_verifier=True)
        kwargs = flow_class.from_client_config.return_value.run_local_server.call_args.kwargs
        self.assertEqual(kwargs["host"], "127.0.0.1")
        self.assertEqual(kwargs["port"], 0)
        self.assertEqual(kwargs["login_hint"], "owner@example.com")
        self.assertFalse(kwargs["open_browser"])


if __name__ == "__main__":
    unittest.main()
