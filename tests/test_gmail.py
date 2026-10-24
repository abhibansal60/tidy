import base64
import contextlib
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock

import requests

from tidy import gmail
from tidy.gmail import APIError, Gmail, RETRY_ATTEMPTS, READ_SCOPE, SCOPES, check_scopes, parse_list_unsubscribe, parse_message, _html_to_text


def response(payload, status=200):
    result = Mock(status_code=status, headers={})
    result.json.return_value = payload
    return result


def b64(text):
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


RAW_MESSAGE = {
    "id": "msg1", "threadId": "thread1", "internalDate": "1700000000000",
    "labelIds": ["INBOX", "UNREAD"],
    "payload": {
        "headers": [
            {"name": "Subject", "value": "Quick question"},
            {"name": "From", "value": "Alice <alice@example.com>"},
            {"name": "To", "value": "owner@example.com"},
            {"name": "List-Unsubscribe", "value": "<mailto:unsub@example.com>"},
        ],
        "mimeType": "text/plain",
        "body": {"data": b64("Hey, can you send the file over? " * 40)},
    },
}


class ScopeTests(unittest.TestCase):
    def test_read_scope_accepted_write_like_scope_rejected(self):
        check_scopes(SCOPES)  # no raise
        with self.assertRaises(APIError):
            check_scopes(["https://www.googleapis.com/auth/gmail.modify"])
        with self.assertRaises(APIError):
            check_scopes([])


class ParseMessageTests(unittest.TestCase):
    def test_flattens_headers_body_and_truncates_snippet(self):
        parsed = parse_message(RAW_MESSAGE)

        self.assertEqual(parsed["id"], "msg1")
        self.assertEqual(parsed["thread_id"], "thread1")
        self.assertEqual(parsed["subject"], "Quick question")
        self.assertEqual(parsed["sender"], "Alice <alice@example.com>")
        self.assertEqual(parsed["to"], "owner@example.com")
        self.assertTrue(parsed["list_unsubscribe"])
        self.assertEqual(parsed["label_ids"], ["INBOX", "UNREAD"])
        self.assertLessEqual(len(parsed["snippet"]), 1000)
        self.assertTrue(parsed["snippet"].startswith("Hey, can you send the file over?"))

    def test_missing_list_unsubscribe_is_false(self):
        raw = {**RAW_MESSAGE, "payload": {**RAW_MESSAGE["payload"],
               "headers": [h for h in RAW_MESSAGE["payload"]["headers"] if h["name"] != "List-Unsubscribe"]}}

        self.assertFalse(parse_message(raw)["list_unsubscribe"])

    def test_multipart_walks_to_text_plain_part(self):
        raw = {**RAW_MESSAGE, "payload": {"headers": RAW_MESSAGE["payload"]["headers"], "mimeType": "multipart/alternative",
               "parts": [{"mimeType": "text/html", "body": {"data": b64("<p>hi</p>")}},
                         {"mimeType": "text/plain", "body": {"data": b64("plain body")}}]}}

        self.assertEqual(parse_message(raw)["snippet"], "plain body")

    def test_html_only_falls_back_to_stripped_html(self):
        raw = {**RAW_MESSAGE, "payload": {"headers": RAW_MESSAGE["payload"]["headers"],
               "mimeType": "text/html", "body": {"data": b64("<p>Please reply today</p>")}}}

        self.assertEqual(parse_message(raw)["snippet"], "Please reply today")

    def test_html_fallback_strips_style_and_script_content_not_just_tags(self):
        body = "<html><head><style>.a{color:red}</style><script>track()</script></head><body>Actual message</body></html>"
        raw = {**RAW_MESSAGE, "payload": {"headers": RAW_MESSAGE["payload"]["headers"],
               "mimeType": "text/html", "body": {"data": b64(body)}}}

        snippet = parse_message(raw)["snippet"]

        self.assertIn("Actual message", snippet)
        self.assertNotIn("color:red", snippet)
        self.assertNotIn("track()", snippet)

    def test_list_unsubscribe_value_and_one_click_are_captured(self):
        headers = RAW_MESSAGE["payload"]["headers"] + [{"name": "List-Unsubscribe-Post", "value": "List-Unsubscribe=One-Click"}]
        raw = {**RAW_MESSAGE, "payload": {**RAW_MESSAGE["payload"], "headers": headers}}

        parsed = parse_message(raw)

        self.assertEqual(parsed["list_unsubscribe_value"], "<mailto:unsub@example.com>")
        self.assertTrue(parsed["list_unsubscribe_one_click"])

    def test_one_click_defaults_false_without_the_header(self):
        self.assertFalse(parse_message(RAW_MESSAGE)["list_unsubscribe_one_click"])


class HtmlToTextTests(unittest.TestCase):
    def test_style_and_script_blocks_are_dropped(self):
        self.assertEqual(_html_to_text("<p>hi</p><STYLE x>a{}</style>there<script>x</SCRIPT>!").split(), ["hi", "there", "!"])
        self.assertEqual(_html_to_text("a<style>never closed").strip(), "a")

    def test_unclosed_style_tags_cannot_stall_a_run(self):
        # The old lazy regex took ~29s on 200 KB of these; any sender could send one.
        started = time.perf_counter()
        _html_to_text("<style>" * 100_000)
        self.assertLess(time.perf_counter() - started, 1)


class ParseListUnsubscribeTests(unittest.TestCase):
    def test_extracts_mailto_and_https(self):
        links = parse_list_unsubscribe("<mailto:unsub@example.com>, <https://example.com/unsub?id=1>")

        self.assertEqual(links, {"mailto": "mailto:unsub@example.com", "http": "https://example.com/unsub?id=1"})

    def test_mailto_only(self):
        self.assertEqual(parse_list_unsubscribe("<mailto:unsub@example.com>"),
                         {"mailto": "mailto:unsub@example.com", "http": None})

    def test_empty_value(self):
        self.assertEqual(parse_list_unsubscribe(""), {"mailto": None, "http": None})
        self.assertEqual(parse_list_unsubscribe(None), {"mailto": None, "http": None})

    def test_html_fallback_unescapes_entities(self):
        raw = {**RAW_MESSAGE, "payload": {"headers": RAW_MESSAGE["payload"]["headers"],
               "mimeType": "text/html", "body": {"data": b64("<p>Fish &amp; chips</p>")}}}

        self.assertEqual(parse_message(raw)["snippet"], "Fish & chips")

    def test_no_body_falls_back_to_gmail_snippet_not_empty(self):
        raw = {**RAW_MESSAGE, "snippet": "Gmail's own short preview",
               "payload": {"headers": RAW_MESSAGE["payload"]["headers"], "mimeType": "text/plain", "body": {}}}

        self.assertEqual(parse_message(raw)["snippet"], "Gmail's own short preview")


class MessageIdsTests(unittest.TestCase):
    def test_pages_until_limit_reached(self):
        session = Mock()
        session.get.side_effect = [
            response({"messages": [{"id": "a"}, {"id": "b"}], "nextPageToken": "p2"}),
            response({"messages": [{"id": "c"}]}),
        ]
        api = Gmail(session)

        ids = api.message_ids("in:inbox", limit=3)

        self.assertEqual(ids, ["a", "b", "c"])
        session.post.assert_not_called()
        session.delete.assert_not_called()

    def test_repeated_page_token_fails_closed(self):
        session = Mock()
        session.get.side_effect = [
            response({"messages": [{"id": "a"}], "nextPageToken": "loop"}),
            response({"messages": [{"id": "b"}], "nextPageToken": "loop"}),
        ]
        api = Gmail(session)

        with self.assertRaises(APIError):
            api.message_ids("in:inbox", limit=10)


class BatchModifyTests(unittest.TestCase):
    def test_archive_removes_inbox_only(self):
        session = Mock()
        session.post.return_value = response(None, status=204)
        api = Gmail(session)

        api.batch_modify(["a", "b"], remove=["INBOX"])

        session.post.assert_called_once()
        body = session.post.call_args.kwargs["json"]
        self.assertEqual(body, {"ids": ["a", "b"], "addLabelIds": [], "removeLabelIds": ["INBOX"]})

    def test_no_op_on_empty_ids(self):
        session = Mock()
        api = Gmail(session)

        api.batch_modify([])

        session.post.assert_not_called()

    def test_rejects_labels_outside_the_allowed_set(self):
        api = Gmail(Mock())
        with self.assertRaises(ValueError):
            api.batch_modify(["a"], remove=["TRASH"])
        with self.assertRaises(ValueError):
            api.batch_modify(["a"], add=["IMPORTANT"])

    def test_non_204_raises(self):
        session = Mock()
        session.post.return_value = response({"error": "nope"}, status=400)
        api = Gmail(session)

        with self.assertRaises(APIError):
            api.batch_modify(["a"], remove=["INBOX"])


class TrashTests(unittest.TestCase):
    def test_success_on_200(self):
        session = Mock()
        session.post.return_value = response(None, status=200)
        api = Gmail(session)

        api.trash("m1")

        session.post.assert_called_once()
        self.assertIn("messages/m1/trash", session.post.call_args.args[0])

    def test_non_200_raises(self):
        session = Mock()
        session.post.return_value = response({"error": "nope"}, status=400)
        api = Gmail(session)

        with self.assertRaises(APIError):
            api.trash("m1")

    def test_rate_limit_retries_then_succeeds(self):
        session = Mock()
        limited = response({"error": {"errors": [{"reason": "rateLimitExceeded"}]}}, status=403)
        session.post.side_effect = [limited, response(None, status=200)]
        api = Gmail(session)

        with unittest.mock.patch("time.sleep"):
            api.trash("m1")

        self.assertEqual(session.post.call_count, 2)


class BudgetTests(unittest.TestCase):
    def test_call_budget_enforced(self):
        session = Mock()
        session.get.return_value = response({"messages": []})
        api = Gmail(session, max_calls=1)

        api.message_ids("in:inbox", limit=1)
        with self.assertRaises(APIError):
            api.message(message_id="x")

    def test_only_get_resources_allowed(self):
        api = Gmail(Mock())
        with self.assertRaises(ValueError):
            api.get("subscriptions")


class MessageIdTests(unittest.TestCase):
    def test_path_like_ids_never_reach_the_api(self):
        session = Mock()
        api = Gmail(session)
        for bad in ("../profile", "m1/trash", "m1?x=1", "", None):
            with self.assertRaises(ValueError):
                api.trash(bad)
            with self.assertRaises(ValueError):
                api.batch_modify([bad], remove=["INBOX"])
        session.post.assert_not_called()

    def test_labels_reads_minimal_format(self):
        session = Mock()
        session.get.return_value = response({"id": "m1", "labelIds": ["INBOX", "STARRED"]})
        api = Gmail(session)

        self.assertEqual(api.labels("m1"), ["INBOX", "STARRED"])
        self.assertEqual(session.get.call_args.kwargs["params"], {"format": "minimal"})


def rate_limited(reason="rateLimitExceeded", retry_after=None):
    result = response({"error": {"errors": [{"reason": reason}]}}, status=403)
    if retry_after is not None:
        result.headers = {"Retry-After": retry_after}
    return result


class RetryTests(unittest.TestCase):
    def setUp(self):
        patcher = unittest.mock.patch("time.sleep")
        self.sleep = patcher.start()
        self.addCleanup(patcher.stop)

    def test_get_retries_429_and_5xx_and_counts_every_attempt(self):
        session = Mock()
        session.get.side_effect = [response({}, 429), response({}, 503), response({"id": "m1"})]
        api = Gmail(session)

        self.assertEqual(api.get("messages/m1"), {"id": "m1"})
        self.assertEqual(api.calls, 3)

    def test_forbidden_that_is_not_a_rate_limit_fails_at_once(self):
        session = Mock()
        session.get.return_value = rate_limited("insufficientPermissions")
        api = Gmail(session)

        with self.assertRaisesRegex(APIError, "HTTP 403"):
            api.get("profile")
        self.assertEqual(session.get.call_count, 1)

    def test_retry_after_is_honoured_but_capped(self):
        session = Mock()
        session.get.side_effect = [rate_limited(retry_after="7"), rate_limited(retry_after="99999"), response({})]

        Gmail(session).get("profile")

        self.assertEqual([c.args[0] for c in self.sleep.call_args_list], [7.0, 120])

    def test_network_errors_give_up_after_the_retry_budget(self):
        session = Mock()
        session.get.side_effect = requests.ConnectionError()

        with self.assertRaisesRegex(APIError, "Network request failed"):
            Gmail(session).get("profile")
        self.assertEqual(session.get.call_count, RETRY_ATTEMPTS)

    def test_bad_json_or_shape_is_an_api_error(self):
        session = Mock()
        session.get.return_value = response(None)
        session.get.return_value.json.side_effect = ValueError()
        with self.assertRaisesRegex(APIError, "invalid JSON"):
            Gmail(session).get("profile")
        session.get.return_value = response(["not", "a", "dict"])
        with self.assertRaisesRegex(APIError, "response shape"):
            Gmail(session).get("profile")

    def test_userinfo_does_not_spend_the_gmail_budget(self):
        session = Mock()
        session.get.return_value = response({"email": "owner@example.com", "email_verified": True, "sub": "1"})
        api = Gmail(session, max_calls=1)

        api.identity("owner@example.com")

        self.assertEqual(api.calls, 0)

    def test_batch_modify_retries_then_reports_a_safe_rerun(self):
        session = Mock()
        session.post.side_effect = [response({}, 500), response(None, 204)]
        Gmail(session).batch_modify(["a"], remove=["INBOX"])
        self.assertEqual(session.post.call_count, 2)

        session = Mock()
        session.post.side_effect = requests.ConnectionError()
        with self.assertRaisesRegex(APIError, "rerun is safe"):
            Gmail(session).batch_modify(["a"], remove=["INBOX"])
        self.assertEqual(session.post.call_count, RETRY_ATTEMPTS)

    def test_mutations_stop_at_the_call_budget_including_retries(self):
        session = Mock()
        session.post.return_value = response({}, 503)
        api = Gmail(session, max_calls=2)

        with self.assertRaisesRegex(APIError, "budget"):
            api.trash("m1")
        self.assertEqual(session.post.call_count, 2)
        with self.assertRaisesRegex(APIError, "budget"):
            api.batch_modify(["a"], remove=["INBOX"])
        self.assertEqual(session.post.call_count, 2)

    def test_trash_network_failure_gives_up_after_the_retry_budget(self):
        session = Mock()
        session.post.side_effect = requests.ConnectionError()

        with self.assertRaisesRegex(APIError, "trash is idempotent"):
            Gmail(session).trash("m1")

    def test_batch_modify_refuses_more_than_1000_ids(self):
        with self.assertRaises(ValueError):
            Gmail(Mock()).batch_modify([f"m{i}" for i in range(1001)], remove=["INBOX"])


class IdentityTests(unittest.TestCase):
    def identity(self, user):
        session = Mock()
        session.get.return_value = response(user)
        return Gmail(session).identity("Owner@Example.com")

    def test_matching_verified_email_returns_subject(self):
        self.assertEqual(self.identity({"email": "owner@example.com", "email_verified": True, "sub": "42"}),
                         {"google_sub": "42", "email": "owner@example.com"})

    def test_other_or_unverified_account_is_refused(self):
        for user in ({"email": "other@example.com", "email_verified": True, "sub": "1"},
                     {"email": "owner@example.com", "email_verified": False, "sub": "1"}):
            with self.assertRaisesRegex(APIError, "does not match"):
                self.identity(user)


class ConnectTests(unittest.TestCase):
    def test_missing_token_names_the_fix(self):
        with self.assertRaisesRegex(ValueError, "mail-auth --write"):
            with gmail.connect("/nonexistent/token_mail_write.json", write=True):
                pass
        with self.assertRaisesRegex(ValueError, "Run mail-auth first"):
            with gmail.connect("/nonexistent/token_mail.json"):
                pass

    def test_checks_the_account_and_saves_the_token_on_exit(self):
        with tempfile.TemporaryDirectory() as d:
            token = Path(d) / "token_mail.json"
            token.write_text("{}")
            session = Mock()
            session.get.return_value = response({"email": "owner@example.com", "email_verified": True, "sub": "1"})
            with unittest.mock.patch.object(gmail, "load_credentials", return_value="creds") as load, \
                    unittest.mock.patch.object(gmail, "session_for", return_value=contextlib.nullcontext(session)), \
                    unittest.mock.patch.object(gmail, "save_credentials") as save:
                with gmail.connect(token, "owner@example.com", max_calls=5) as api:
                    self.assertEqual(api.max_calls, 5)
            load.assert_called_once_with(token, False)
            save.assert_called_once_with(token, "creds", False)

    def test_wrong_account_raises_and_does_not_save(self):
        with tempfile.TemporaryDirectory() as d:
            token = Path(d) / "token_mail_write.json"
            token.write_text("{}")
            session = Mock()
            session.get.return_value = response({"email": "other@example.com", "email_verified": True, "sub": "1"})
            with unittest.mock.patch.object(gmail, "load_credentials", return_value="creds"), \
                    unittest.mock.patch.object(gmail, "session_for", return_value=contextlib.nullcontext(session)), \
                    unittest.mock.patch.object(gmail, "save_credentials") as save:
                with self.assertRaises(APIError):
                    with gmail.connect(token, "owner@example.com", write=True):
                        self.fail("must not yield a client for another account")
            save.assert_not_called()
