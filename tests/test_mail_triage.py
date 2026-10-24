"""`mail.triage`, the path the scheduled `mail-triage --execute --apply --override-gate` run takes."""

import unittest
from unittest.mock import Mock

from typesafe_sdk import TypeSafeError

from tidy.gmail import APIError
from tidy.mail import triage
from test_mail import OWNER, answer


def raw(id, subject, labels=("INBOX", "CATEGORY_UPDATES"), unsubscribe=True, to=OWNER):
    headers = [{"name": "Subject", "value": subject}, {"name": "From", "value": f"Sender <{id}@example.com>"},
               {"name": "To", "value": to}]
    if unsubscribe:
        headers.append({"name": "List-Unsubscribe", "value": f"<https://example.com/u/{id}>"})
    return {"id": id, "threadId": "t-" + id, "internalDate": "1700000000000", "labelIds": list(labels),
            "snippet": subject, "payload": {"headers": headers}}


class FakeInbox:
    """Read-only Gmail stand-in: the messages a query returns, in order."""
    def __init__(self, *messages):
        self.by_id = {m["id"]: m for m in messages}
        self.queries = []

    def message_ids(self, query, limit):
        self.queries.append((query, limit))
        return list(self.by_id)[:limit]

    def message(self, message_id):
        return self.by_id[message_id]


class SubjectClient:
    """Jev stand-in that answers by subject: {subject: category or TypeSafeError}."""
    def __init__(self, by_subject):
        def reply(state, questions):
            choice = by_subject[state["subject"]]
            if isinstance(choice, Exception):
                raise choice
            return answer(choice=choice, confidence=0.95)
        self.system_one = Mock(side_effect=reply)


def inbox():
    """One message per proposed action: archive (corroborated Updates), trash, spam, keep, plus starred bulk mail."""
    return FakeInbox(raw("arch1", "Your order shipped"), raw("arch2", "Statement ready"),
                     raw("promo", "50% off"), raw("spam", "You won"), raw("reply", "Lunch?", ("INBOX",), False),
                     raw("star", "Starred receipt", ("INBOX", "CATEGORY_UPDATES", "STARRED")))


CATEGORY = {"Your order shipped": "Updates", "Statement ready": "Updates", "50% off": "Promos", "You won": "Spam",
            "Lunch?": "Needs Reply", "Starred receipt": "Updates"}


def writer(calls=0, max_calls=1000):
    return Mock(calls=calls, max_calls=max_calls)


class TriageTests(unittest.TestCase):
    """The cron path: `mail-triage --execute --apply --override-gate`. Only corroborated ARCHIVE ever reaches Gmail."""

    def run_triage(self, write_api=None, **kw):
        return triage(inbox(), SubjectClient(CATEGORY), OWNER, "in:inbox", 50, write_api=write_api, **kw)

    def outcome(self, out):
        return {r["id"]: (r["action"], r["outcome"]) for r in out["rows"]}

    def test_without_a_write_api_nothing_is_applied_or_marked(self):
        out = self.run_triage(cap_archive=100, override_gate=True)

        self.assertFalse(out["applied"])
        self.assertIsNone(out["outcome_counts"])
        self.assertTrue(all(r["outcome"] is None for r in out["rows"]))
        self.assertEqual(out["action_counts"], {"ARCHIVE": 2, "TRASH": 1, "SPAM": 1, "KEEP": 2})

    def test_closed_gate_without_override_never_touches_gmail(self):
        api = writer()

        out = self.run_triage(api, cap_archive=100)

        api.batch_modify.assert_not_called()
        api.trash.assert_not_called()
        self.assertFalse(out["gate_overridden"])
        self.assertEqual(out["outcome_counts"], {"applied": 0, "held": 4})

    def test_override_archives_only_corroborated_bulk_mail_and_holds_trash_and_spam(self):
        api = writer()

        out = self.run_triage(api, cap_archive=100, override_gate=True)

        api.batch_modify.assert_called_once_with(["arch1", "arch2"], add=[], remove=["INBOX"])
        api.trash.assert_not_called()
        self.assertTrue(out["gate_overridden"])
        self.assertEqual(self.outcome(out), {
            "arch1": ("ARCHIVE", "applied"), "arch2": ("ARCHIVE", "applied"), "promo": ("TRASH", "held"),
            "spam": ("SPAM", "held"), "reply": ("KEEP", None), "star": ("KEEP", None)})
        self.assertIsNone(out["mutation_errors"])

    def test_starred_bulk_mail_is_never_archived(self):
        api = writer()

        out = self.run_triage(api, cap_archive=100, override_gate=True)

        self.assertNotIn("star", api.batch_modify.call_args.args[0])
        self.assertIn("owner-protected (STARRED)", next(r for r in out["rows"] if r["id"] == "star")["signals"][0])

    def test_cap_limits_archives_and_holds_the_rest(self):
        api = writer()

        out = self.run_triage(api, cap_archive=1, override_gate=True)

        api.batch_modify.assert_called_once_with(["arch1"], add=[], remove=["INBOX"])
        self.assertEqual(self.outcome(out)["arch2"], ("ARCHIVE", "held"))

    def test_default_cap_of_zero_applies_nothing(self):
        api = writer()

        self.run_triage(api, override_gate=True)

        api.batch_modify.assert_not_called()

    def test_negative_cap_refuses_before_reading_gmail(self):
        box = inbox()
        with self.assertRaises(ValueError):
            triage(box, SubjectClient(CATEGORY), OWNER, "in:inbox", 50, write_api=writer(), cap_archive=-1)
        self.assertEqual(box.queries, [])

    def test_jev_error_drops_the_message_from_rows_and_from_apply(self):
        categories = {**CATEGORY, "Your order shipped": TypeSafeError("timeout")}
        api = writer()

        out = triage(inbox(), SubjectClient(categories), OWNER, "in:inbox", 50, write_api=api, cap_archive=100,
                     override_gate=True)

        self.assertEqual(out["errors"], {"arch1": "timeout"})
        self.assertNotIn("arch1", {r["id"] for r in out["rows"]})
        api.batch_modify.assert_called_once_with(["arch2"], add=[], remove=["INBOX"])

    def test_failed_archive_is_reported_not_raised(self):
        api = writer()
        api.batch_modify.side_effect = APIError("HTTP 500")

        out = self.run_triage(api, cap_archive=100, override_gate=True)

        self.assertEqual(set(out["mutation_errors"]), {"arch1", "arch2"})
        self.assertTrue(self.outcome(out)["arch1"][1].startswith("error"))

    def test_too_small_write_budget_applies_nothing(self):
        api = writer(calls=1000, max_calls=1000)

        with self.assertRaisesRegex(ValueError, "Nothing was applied"):
            self.run_triage(api, cap_archive=100, override_gate=True)
        api.batch_modify.assert_not_called()


if __name__ == "__main__":
    unittest.main()
