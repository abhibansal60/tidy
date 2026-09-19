from dataclasses import replace
from pathlib import Path
import unittest

from tidy import policy, profile
from tidy.judge import Judgment
from test_evidence_store import sample

PROFILE = profile.load(Path("/nonexistent/profile.json"))  # defaults: low<1.0, keep>=2.0, packaging>=0.7, sufficiency>=0.5, confidence>=0.5


def judgment(rel=3.0, val=3.0, pack=0.1, suff=0.9, rel_conf=0.9, val_conf=0.9, evidence_hash="h1"):
    answers = {"relevance": {"score": rel, "confidence": rel_conf}, "apparent_value": {"score": val, "confidence": val_conf},
               "packaging_risk": {"noul": pack}, "evidence_sufficiency": {"noul": suff}}
    return Judgment("chanA", evidence_hash, "titles-v1", "m", answers, {}, 1, "2026-09-20T00:00:00+00:00")


class PolicyTests(unittest.TestCase):
    # (name, judgment kwargs, sample overrides, status, expected action, signal fragments that must appear)
    TABLE = [
        ("strong channel", {}, {}, "active", "KEEP", []),
        ("low relevance and low value, evidence sufficient", {"rel": 0.4, "val": 0.6}, {}, "active", "UNSUBSCRIBE",
         ["relevance low (0.4)", "value low (0.6)"]),
        ("same but thin evidence never unsubscribes", {"rel": 0.4, "val": 0.6, "suff": 0.2}, {}, "active", "REVIEW",
         ["evidence thin (0.2)"]),
        ("entertainment: low relevance alone", {"rel": 0.2}, {}, "active", "WATCH", ["relevance low (0.2)"]),
        ("low value alone needs a look", {"val": 0.5}, {}, "active", "REVIEW", ["value low (0.5)"]),
        ("packaging alone never unsubscribes", {"pack": 0.9}, {}, "active", "REVIEW", ["packaging high (0.9)"]),
        ("packaging plus low relevance is still not two quality signals", {"rel": 0.5, "pack": 0.9}, {}, "active",
         "REVIEW", ["packaging high (0.9)"]),
        ("all three negative", {"rel": 0.5, "val": 0.5, "pack": 0.9}, {}, "active", "UNSUBSCRIBE",
         ["relevance low (0.5)", "value low (0.5)", "packaging high (0.9)"]),
        ("unsure distributions block unsubscribe", {"rel": 0.5, "val": 0.5, "rel_conf": 0.3}, {}, "active", "REVIEW",
         ["relevance confidence low (0.3)"]),
        ("middling everything", {"rel": 1.5, "val": 1.5}, {}, "active", "WATCH", []),
        ("trial follows the same rules", {"rel": 0.4, "val": 0.6}, {}, "trial", "UNSUBSCRIBE", ["on trial"]),
        ("stale channel is flagged, not negative", {}, {"newest_published_at": "2025-08-01T00:00:00Z"}, "active",
         "KEEP", ["stale: newest upload 415 days old"]),
        ("empty channel is flagged and reviewed", {"suff": 0.1},
         {"videos": [], "newest_published_at": None, "coverage": {"requested": 12, "collected": 0, "unavailable": 0}},
         "active", "REVIEW", ["no recent uploads"]),
    ]

    def test_table(self):
        for name, jkw, skw, status, action, fragments in self.TABLE:
            with self.subTest(name):
                p = policy.propose(judgment(**jkw), replace(sample(), **skw), PROFILE, status)
                self.assertEqual(p.action, action)
                for fragment in fragments:
                    self.assertIn(fragment, p.signals)

    def test_proposal_is_tied_to_evidence_and_policy_version(self):
        p = policy.propose(judgment(evidence_hash="abc"), sample(), PROFILE, "active")
        self.assertEqual((p.channel_id, p.evidence_hash, p.policy_version), ("chanA", "abc", policy.POLICY_VERSION))

    def test_thresholds_come_from_profile(self):
        strict = {**PROFILE, "thresholds": {**PROFILE["thresholds"], "relevance_low": 2.5}}
        self.assertEqual(policy.propose(judgment(rel=2.0, val=0.5), sample(), PROFILE, "active").action, "REVIEW")
        self.assertEqual(policy.propose(judgment(rel=2.0, val=0.5), sample(), strict, "active").action, "UNSUBSCRIBE")


class WatchPolicyTests(unittest.TestCase):
    """policy-2: revealed watching plus a strict two-opinion low-quality cascade."""

    def setUp(self):
        self.profile = profile.load(Path("/nonexistent/profile.json"))

    def run_policy(self, val, watched, second=None):
        return policy.propose_watch(judgment(val=val), sample(), self.profile, watched, second)

    def test_low_quality_confirmed_by_second_opinion_is_unsubscribe_even_if_watched(self):
        p = self.run_policy(0.3, watched=9, second={"apparent_value": 0.4})

        self.assertEqual(p.action, "UNSUBSCRIBE")
        self.assertEqual(p.signals, ["value low, Jev (0.3)", "value low, second opinion (0.4)",
                                     "watched 9 times in 42 days"])
        self.assertEqual(p.policy_version, "policy-2")

    def test_low_quality_without_second_opinion_only_asks_for_one(self):
        p = self.run_policy(0.3, watched=0)

        self.assertEqual((p.action, p.signals), ("REVIEW", ["value low, Jev (0.3)", "needs second opinion"]))

    def test_second_opinion_that_disagrees_blocks_the_unsubscribe(self):
        p = self.run_policy(0.3, watched=0, second={"apparent_value": 0.9})

        self.assertEqual(p.action, "REVIEW")
        self.assertIn("second opinion disagrees (0.9)", p.signals)

    def test_watched_channels_are_kept_and_unwatched_ones_go_to_review(self):
        self.assertEqual(self.run_policy(1.4, watched=3).action, "KEEP")
        unwatched = self.run_policy(2.4, watched=0)
        self.assertEqual((unwatched.action, unwatched.signals),
                         ("REVIEW", ["unwatched in 42 days", "quality high: watch it or drop it"]))
        self.assertEqual(self.run_policy(1.4, watched=0).signals, ["unwatched in 42 days"])

    def test_window_and_threshold_come_from_the_profile(self):
        custom = {**self.profile, "watch_window_days": 30, "low_quality_value": 0.2}

        p = policy.propose_watch(judgment(val=0.3), sample(), custom, 0)

        self.assertEqual(p.signals, ["unwatched in 30 days"])


class SubscribeTests(unittest.TestCase):
    def test_subscribe_needs_high_quality_and_repeat_watching(self):
        for name, val, watched, expected in [("good and watched often", 2.5, 4, "SUBSCRIBE"),
                                             ("watched but middling quality", 1.5, 6, None),
                                             ("good but watched too little", 3.0, 1, None),
                                             ("exactly the minimums", 2.0, 3, "SUBSCRIBE")]:
            with self.subTest(name):
                p = policy.propose_subscribe(judgment(val=val), watched, PROFILE)
                self.assertEqual(p and p.action, expected)

    def test_subscribe_signals_show_the_evidence_and_policy(self):
        p = policy.propose_subscribe(judgment(val=2.5, evidence_hash="abc"), 4, PROFILE)

        self.assertEqual(p.signals, ["value high (2.5)", "watched 4 times in 42 days, not subscribed"])
        self.assertEqual((p.channel_id, p.evidence_hash, p.policy_version), ("chanA", "abc", "policy-2"))
