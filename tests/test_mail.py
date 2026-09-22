from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from typesafe_sdk import ChoiceAnswer, SystemOneResponse, TypeSafeError, Usage

from tidy import store
from tidy.gmail import APIError
from tidy.mail import (ACTION_FOR_CATEGORY, CATEGORIES, MailProposal, apply, classify, classify_batch,
                       evidence_hash, gate_status, propose, recheck, select_held)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def message(**overrides):
    base = {"id": "m1", "thread_id": "t1", "subject": "Can you review this?", "sender": "Alice <a@example.com>",
            "to": "owner@example.com", "cc": "", "list_unsubscribe": False, "snippet": "please take a look"}
    return {**base, **overrides}


def answer(choice="Needs Reply", confidence=0.9, probabilities=None):
    probabilities = probabilities or {choice: confidence}
    return SystemOneResponse(model="jev-test-1", usage=Usage(input_tokens=300, output_tokens=5),
                             answers={"category": ChoiceAnswer(choice=choice, confidence=confidence,
                                                               probabilities=probabilities)})


class FakeClient:
    def __init__(self, reply=None):
        self.system_one = Mock(side_effect=lambda **kw: reply or answer())


OWNER = "owner@example.com"


class ClassifyTests(unittest.TestCase):
    def test_bundles_one_call_with_state_and_category_question(self):
        client = FakeClient(answer(choice="Updates", confidence=0.8, probabilities={"Updates": 0.8, "Promos": 0.2}))

        result = classify(client, message(list_unsubscribe=True, to="a@x.com,b@x.com"), OWNER)

        self.assertEqual(client.system_one.call_count, 1)
        state = client.system_one.call_args.kwargs["state"]
        self.assertEqual(state["subject"], "Can you review this?")
        self.assertEqual(state["facts"]["list_unsubscribe_header"], True)
        self.assertEqual(state["facts"]["addressed_directly"], False)  # multiple recipients, neither is the owner
        self.assertEqual(result.message_id, "m1")
        self.assertEqual(result.thread_id, "t1")
        self.assertEqual(result.category, "Updates")
        self.assertEqual(result.confidence, 0.8)
        self.assertEqual(result.usage, {"input_tokens": 300, "output_tokens": 5})
        self.assertEqual(result.facts, state["facts"])

    def test_single_recipient_is_addressed_directly_only_when_it_is_the_owner(self):
        client = FakeClient()

        classify(client, message(to=OWNER), OWNER)
        self.assertTrue(client.system_one.call_args.kwargs["state"]["facts"]["addressed_directly"])

        classify(client, message(to="someone.else@example.com"), OWNER)
        self.assertFalse(client.system_one.call_args.kwargs["state"]["facts"]["addressed_directly"])

    def test_owner_only_in_cc_is_not_addressed_directly(self):
        client = FakeClient()

        classify(client, message(to="colleague@example.com", cc=OWNER), OWNER)

        self.assertFalse(client.system_one.call_args.kwargs["state"]["facts"]["addressed_directly"])

    def test_api_error_returned_as_string_not_raised(self):
        client = Mock()
        client.system_one.side_effect = TypeSafeError("rate limited")

        result = classify(client, message(), OWNER)

        self.assertEqual(result, "rate limited")

    def test_every_category_has_a_policy_action(self):
        self.assertEqual(set(CATEGORIES), set(ACTION_FOR_CATEGORY))


class ProposeTests(unittest.TestCase):
    def test_confident_category_maps_to_its_action(self):
        judgment = classify(FakeClient(answer(choice="Spam", confidence=0.95)), message(), OWNER)

        proposal = propose(judgment)

        self.assertEqual(proposal.action, "SPAM")
        self.assertEqual(proposal.category, "Spam")

    def test_low_confidence_goes_to_review_not_the_category_action(self):
        judgment = classify(FakeClient(answer(choice="Promos", confidence=0.4)), message(), OWNER)

        proposal = propose(judgment)

        self.assertEqual(proposal.action, "REVIEW")

    def test_updates_promos_split_with_no_reply_signal_archives_not_trashes(self):
        split = {"Updates": 0.52, "Promos": 0.46, "Needs Reply": 0.01, "Spam": 0.01}
        judgment = classify(FakeClient(answer(choice="Updates", confidence=0.45, probabilities=split)),
                            message(list_unsubscribe=True), OWNER)

        proposal = propose(judgment)

        self.assertEqual(proposal.action, "ARCHIVE")
        self.assertIn("bulk split", proposal.signals[0])

    def test_split_with_some_needs_reply_mass_still_goes_to_review(self):
        split = {"Updates": 0.55, "Promos": 0.36, "Needs Reply": 0.09}
        judgment = classify(FakeClient(answer(choice="Updates", confidence=0.45, probabilities=split)),
                            message(list_unsubscribe=True), OWNER)

        self.assertEqual(propose(judgment).action, "REVIEW")

    def test_bulk_split_still_needs_a_corroborating_signal(self):
        split = {"Updates": 0.5, "Promos": 0.5}
        judgment = classify(FakeClient(answer(choice="Promos", confidence=0.5, probabilities=split)),
                            message(to=OWNER), OWNER)

        self.assertEqual(propose(judgment).action, "REVIEW")

    def test_needs_reply_never_auto_actioned(self):
        judgment = classify(FakeClient(answer(choice="Needs Reply", confidence=0.99)), message(), OWNER)

        self.assertEqual(propose(judgment).action, "KEEP")

    def test_archive_needs_a_corroborating_signal_not_just_confidence(self):
        # Personally addressed, no unsubscribe header: looks like a real 1:1 email, not bulk mail.
        # Jev alone is not enough to auto-archive (AGENTS.md/ADR 0005: never on one dimension alone).
        judgment = classify(FakeClient(answer(choice="Updates", confidence=0.95)), message(to=OWNER), OWNER)

        proposal = propose(judgment)

        self.assertEqual(proposal.action, "REVIEW")
        self.assertIn("no independent corroborating signal", proposal.signals[-1])

    def test_gmail_bulk_tab_counts_as_a_corroborating_signal(self):
        judgment = classify(FakeClient(answer(choice="Updates", confidence=0.95)), message(to=OWNER), OWNER)

        proposal = propose(judgment, ["INBOX", "CATEGORY_UPDATES"])

        self.assertEqual(proposal.action, "ARCHIVE")
        self.assertIn("Gmail tab", proposal.signals[-1])

    def test_archive_proceeds_with_a_corroborating_signal(self):
        judgment = classify(FakeClient(answer(choice="Updates", confidence=0.95)),
                            message(to=OWNER, list_unsubscribe=True), OWNER)

        self.assertEqual(propose(judgment).action, "ARCHIVE")


class ProtectedLabelTests(unittest.TestCase):
    def test_starred_mail_is_never_proposed_for_any_action(self):
        for choice in ("Spam", "Promos", "Updates"):
            judgment = classify(FakeClient(answer(choice=choice, confidence=0.99)), message(list_unsubscribe=True), OWNER)
            proposal = propose(judgment, ["INBOX", "STARRED"])
            self.assertEqual(proposal.action, "KEEP")
            self.assertIn("owner-protected", proposal.signals[0])

    def test_unstarred_labels_change_nothing(self):
        judgment = classify(FakeClient(answer(choice="Spam", confidence=0.95)), message(), OWNER)
        self.assertEqual(propose(judgment, ["INBOX", "CATEGORY_PROMOTIONS"]).action, "SPAM")


class SelectHeldTests(unittest.TestCase):
    def test_newest_run_decides_regardless_of_argument_order(self):
        old = {"run_at": "2026-09-20T08:00:00+00:00", "rows": [{"id": "m1", "action": "TRASH"}]}
        new = {"run_at": "2026-09-21T08:00:00+00:00", "rows": [{"id": "m1", "action": "KEEP"}]}

        self.assertEqual(select_held([new, old], ["TRASH", "SPAM"]), [])

    def test_applied_in_any_run_is_never_reapplied_without_force(self):
        old = {"run_at": "2026-09-20", "rows": [{"id": "m1", "action": "TRASH", "outcome": "applied"}]}
        new = {"run_at": "2026-09-21", "rows": [{"id": "m1", "action": "TRASH", "outcome": "held"}]}

        self.assertEqual(select_held([old, new], ["TRASH"]), [])
        self.assertEqual([r["id"] for r in select_held([old, new], ["TRASH"], force_reapply=True)], ["m1"])

    def test_returns_the_row_objects_so_outcomes_can_be_recorded_in_place(self):
        doc = {"rows": [{"id": "m1", "action": "SPAM"}]}

        select_held([doc], ["SPAM"])[0]["outcome"] = "applied"

        self.assertEqual(doc["rows"][0]["outcome"], "applied")


class RecheckTests(unittest.TestCase):
    def test_skips_messages_moved_or_starred_since_the_run(self):
        api = Mock()
        api.labels.side_effect = lambda i: {"m1": ["INBOX"], "m2": ["TRASH"], "m3": ["INBOX", "STARRED"]}[i]

        valid, skipped = recheck(api, [("m1", "TRASH"), ("m2", "TRASH"), ("m3", "SPAM"), ("m4", "KEEP")])

        self.assertEqual(valid, [("m1", "TRASH")])
        self.assertEqual(skipped, {"m2": "skipped: no longer in inbox", "m3": "skipped: starred since the run"})
        self.assertEqual(api.labels.call_count, 3)  # KEEP never rechecked, never applied

    def test_failed_recheck_skips_rather_than_applies(self):
        api = Mock()
        api.labels.side_effect = APIError("404")

        valid, skipped = recheck(api, [("m1", "TRASH")])

        self.assertEqual(valid, [])
        self.assertIn("could not recheck", skipped["m1"])


def mock_api(calls=0, max_calls=10_000):
    return Mock(calls=calls, max_calls=max_calls)


class ApplyTests(unittest.TestCase):
    def test_groups_archive_and_spam_into_one_batch_call_each(self):
        api = mock_api()
        pairs = [("m1", "ARCHIVE"), ("m2", "ARCHIVE"), ("m3", "SPAM"), ("m4", "KEEP"), ("m5", "REVIEW")]

        outcomes = apply(api, pairs)

        self.assertEqual(api.batch_modify.call_count, 2)
        api.batch_modify.assert_any_call(["m1", "m2"], add=[], remove=["INBOX"])
        api.batch_modify.assert_any_call(["m3"], add=["SPAM"], remove=["INBOX"])
        api.trash.assert_not_called()
        self.assertEqual(outcomes, {"m1": "applied", "m2": "applied", "m3": "applied"})

    def test_trash_calls_the_dedicated_endpoint_per_message_not_batch(self):
        api = mock_api()

        outcomes = apply(api, [("m1", "TRASH"), ("m2", "TRASH")])

        api.batch_modify.assert_not_called()
        self.assertEqual(api.trash.call_count, 2)
        api.trash.assert_any_call("m1")
        api.trash.assert_any_call("m2")
        self.assertEqual(outcomes, {"m1": "applied", "m2": "applied"})

    def test_keep_and_review_never_call_the_api(self):
        api = mock_api()

        apply(api, [("m1", "KEEP"), ("m2", "REVIEW")])

        api.batch_modify.assert_not_called()
        api.trash.assert_not_called()

    def test_more_than_1000_ids_split_into_multiple_batch_calls(self):
        api = mock_api()
        pairs = [(f"m{i}", "ARCHIVE") for i in range(1500)]

        outcomes = apply(api, pairs)

        self.assertEqual(api.batch_modify.call_count, 2)
        first, second = (c.args[0] for c in api.batch_modify.call_args_list)
        self.assertEqual(len(first), 1000)
        self.assertEqual(len(second), 500)
        self.assertEqual(len(outcomes), 1500)

    def test_insufficient_call_budget_refuses_before_touching_the_api(self):
        api = mock_api(calls=999, max_calls=1000)  # 1 call left, but 2 TRASH messages need 2

        with self.assertRaises(ValueError):
            apply(api, [("m1", "TRASH"), ("m2", "TRASH")])

        api.trash.assert_not_called()
        api.batch_modify.assert_not_called()

    def test_one_failed_batch_does_not_lose_outcomes_from_others(self):
        api = mock_api()
        api.batch_modify.side_effect = [None, APIError("quota exceeded")]  # ARCHIVE ok, SPAM fails

        outcomes = apply(api, [("m1", "ARCHIVE"), ("m2", "SPAM")])

        self.assertEqual(outcomes["m1"], "applied")
        self.assertIn("error", outcomes["m2"])
        self.assertIn("quota exceeded", outcomes["m2"])

    def test_one_failed_trash_does_not_stop_the_rest(self):
        api = mock_api()
        api.trash.side_effect = [APIError("network"), None]

        outcomes = apply(api, [("m1", "TRASH"), ("m2", "TRASH")])

        self.assertIn("error", outcomes["m1"])
        self.assertEqual(outcomes["m2"], "applied")


class GateStatusTests(unittest.TestCase):
    def test_always_closed_with_no_mail_labels(self):
        status = gate_status()

        self.assertFalse(status["open"])
        self.assertTrue(status["reasons"])

    def test_promos_and_sales_now_propose_trash_not_archive(self):
        # TRASH is not an AUTO_ACTION (always held for `mail-act` review), so no corroboration is required here.
        judgment = classify(FakeClient(answer(choice="Promos", confidence=0.9)), message(), OWNER)
        self.assertEqual(propose(judgment).action, "TRASH")

        judgment = classify(FakeClient(answer(choice="Sales", confidence=0.9)), message(), OWNER)
        self.assertEqual(propose(judgment).action, "TRASH")

    def test_updates_still_proposes_archive_with_corroboration(self):
        judgment = classify(FakeClient(answer(choice="Updates", confidence=0.9)),
                            message(list_unsubscribe=True), OWNER)
        self.assertEqual(propose(judgment).action, "ARCHIVE")


class EvidenceHashTests(unittest.TestCase):
    def test_same_message_and_owner_hash_the_same(self):
        self.assertEqual(evidence_hash(message(), OWNER), evidence_hash(message(), OWNER))

    def test_different_snippet_hashes_differently(self):
        self.assertNotEqual(evidence_hash(message(), OWNER), evidence_hash(message(snippet="other"), OWNER))

    def test_different_owner_hashes_differently(self):
        self.assertNotEqual(evidence_hash(message(to=OWNER), OWNER),
                            evidence_hash(message(to=OWNER), "someone.else@example.com"))


class ClassifyBatchCachedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = store.connect(Path(self.temp.name) / "inventory.sqlite3")

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_unchanged_evidence_costs_no_second_call(self):
        client = FakeClient()

        first = classify_batch(client, [message()], OWNER, db=self.db, now=NOW)
        again = classify_batch(client, [message()], OWNER, db=self.db, now=NOW)

        self.assertEqual(client.system_one.call_count, 1)
        self.assertEqual(again["m1"], first["m1"])

    def test_changed_message_or_expiry_triggers_a_new_call(self):
        client = FakeClient()
        classify_batch(client, [message()], OWNER, db=self.db, now=NOW)

        classify_batch(client, [message(snippet="different")], OWNER, db=self.db, now=NOW)
        self.assertEqual(client.system_one.call_count, 2)

        classify_batch(client, [message()], OWNER, db=self.db, now=NOW + timedelta(days=31))
        self.assertEqual(client.system_one.call_count, 3)

    def test_without_db_never_caches(self):
        client = FakeClient()

        classify_batch(client, [message()], OWNER, db=None, now=NOW)
        classify_batch(client, [message()], OWNER, db=None, now=NOW)

        self.assertEqual(client.system_one.call_count, 2)

    def test_error_outcome_is_not_cached(self):
        client = Mock()
        client.system_one.side_effect = TypeSafeError("rate limited")

        classify_batch(client, [message()], OWNER, db=self.db, now=NOW)
        classify_batch(client, [message()], OWNER, db=self.db, now=NOW)

        self.assertEqual(client.system_one.call_count, 2)
