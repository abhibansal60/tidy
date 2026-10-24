"""Per-action calibration gate (ADR 0005, docs/options/gated-auto-actions.md): behind `--per-action-gate`."""

import argparse
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tidy import profile, review, store
from tidy.__main__ import main, run_act
from tidy.proposal import Proposal

CONFIG = profile.load(Path("/nonexistent/profile.json"))  # defaults: 30 labels, 85% agreement
HELD = [c for c in (f"chan{i}" for i in range(400)) if review.held_out(c)]
TUNING = [c for c in (f"chan{i}" for i in range(400)) if not review.held_out(c)]


def prop(channel, action):
    return Proposal(channel, action, ["value low (0.2)", "relevance low (0.1)"])


class LabelDb(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = store.connect(Path(self.temp.name) / "inventory.sqlite3")

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def labeled(self, pairs):
        """pairs: (channel, proposed action, owner verdict)."""
        for channel, _, verdict in pairs:
            review.label(self.db, channel, verdict)
        return [prop(channel, action) for channel, action, _ in pairs]


class ActionGateTests(LabelDb):
    def test_split_is_stable_and_about_a_third(self):
        self.assertEqual(review.held_out("chan1"), review.held_out("chan1"))
        self.assertTrue(110 <= len(HELD) <= 160)

    def test_keep_matches_alone_open_the_pooled_gate_but_not_unsubscribe(self):
        proposals = self.labeled([(c, "KEEP", "keep") for c in HELD[:30]])

        pooled = review.gate_status(review.agreement(self.db, proposals), CONFIG)
        per = review.action_gates(self.db, proposals, CONFIG)

        self.assertTrue(pooled["open"])
        self.assertFalse(per["UNSUBSCRIBE"]["gate"]["open"])
        self.assertEqual(per["UNSUBSCRIBE"]["n"], 0)

    def test_unsubscribe_gate_is_precision_on_held_out_labels(self):
        pairs = [(c, "UNSUBSCRIBE", "drop") for c in HELD[:26]] + [(c, "UNSUBSCRIBE", "keep") for c in HELD[26:30]]
        per = review.action_gates(self.db, self.labeled(pairs), CONFIG)

        self.assertEqual((per["UNSUBSCRIBE"]["n"], per["UNSUBSCRIBE"]["agreements"]), (30, 26))
        self.assertTrue(per["UNSUBSCRIBE"]["gate"]["open"])  # 26/30 = 0.867
        self.assertFalse(per["SUBSCRIBE"]["gate"]["open"])  # subscribe needs labels of its own

    def test_labels_outside_the_held_out_third_do_not_count(self):
        proposals = self.labeled([(c, "UNSUBSCRIBE", "drop") for c in TUNING[:40]])

        per = review.action_gates(self.db, proposals, CONFIG)

        self.assertEqual(per["UNSUBSCRIBE"]["n"], 0)
        self.assertFalse(per["UNSUBSCRIBE"]["gate"]["open"])

    def test_subscribe_agrees_with_keep_and_unsure_is_ignored(self):
        pairs = [(c, "SUBSCRIBE", "keep") for c in HELD[:30]] + [(HELD[30], "SUBSCRIBE", "unsure")]
        per = review.action_gates(self.db, self.labeled(pairs), CONFIG)

        self.assertEqual(per["SUBSCRIBE"]["n"], 30)
        self.assertTrue(per["SUBSCRIBE"]["gate"]["open"])


class RunActGateTests(LabelDb):
    """`act --execute`: the per-action check replaces the pooled one only with --per-action-gate."""

    def args(self, **kw):
        path = Path(self.temp.name) / "p.json"
        path.write_text(json.dumps([{"channel_id": HELD[0], "action": "UNSUBSCRIBE", "signals": ["a", "b"]}]))
        base = dict(command="act", proposals=path, gate_unsubscribe=True, gate_subscribe=False, execute=True,
                    override_gate=False, per_action_gate=False, cap_unsubscribe=None, cap_subscribe=None)
        return argparse.Namespace(**{**base, **kw})

    def run_act(self, proposals, **kw):
        with patch.object(review, "derive", return_value=(proposals, [], [])), \
                patch("tidy.mutate.act", return_value={"acted": True}) as act:
            return run_act(self.db, None, "owner@example.com", self.args(**kw), CONFIG), act

    def test_without_the_flag_the_pooled_gate_still_decides(self):
        out, act = self.run_act(self.labeled([(c, "KEEP", "keep") for c in HELD[:30]]))

        self.assertEqual(out, {"acted": True})
        act.assert_called_once()

    def test_flag_refuses_unsubscribe_when_only_keep_matches_exist(self):
        proposals = self.labeled([(c, "KEEP", "keep") for c in HELD[:30]])

        with self.assertRaisesRegex(ValueError, "UNSUBSCRIBE: 0 labels, need 30"):
            self.run_act(proposals, per_action_gate=True)

    def test_flag_checks_only_the_gates_the_owner_opened(self):
        proposals = self.labeled([(c, "UNSUBSCRIBE", "drop") for c in HELD[:30]])
        out, act = self.run_act(proposals, per_action_gate=True)
        act.assert_called_once()

        with self.assertRaises(ValueError) as caught:
            self.run_act(proposals, per_action_gate=True, gate_subscribe=True)
        self.assertEqual(str(caught.exception), "Calibration gate closed: SUBSCRIBE: 0 labels, need 30. "
                                                "Pass --override-gate to act anyway.")

    def test_override_skips_the_check(self):
        out, act = self.run_act([], per_action_gate=True, override_gate=True)
        act.assert_called_once()



class GateCliTests(unittest.TestCase):
    def test_gate_per_action_adds_both_action_types(self):
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(["--data-dir", d, "gate", "--per-action"]), 0)
            self.assertEqual(main(["--data-dir", d, "gate"]), 0)
        with_flag, without = out.getvalue().split("\n}\n")[:2]
        self.assertEqual(set(json.loads(with_flag + "}")["per_action"]), {"UNSUBSCRIBE", "SUBSCRIBE"})
        self.assertNotIn("per_action", without)


if __name__ == "__main__":
    unittest.main()
