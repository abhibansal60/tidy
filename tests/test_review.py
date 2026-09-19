import contextlib
from datetime import datetime, timezone
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest

from typesafe_sdk import ScoreAnswer

from tidy import profile, review, store
from tidy.__main__ import main
from tidy.collector import CollectResult
from tidy.judge import judge
from tidy.proposal import Proposal
from test_evidence_store import sample
from test_judge import FakeClient, response
from test_policy import PROFILE, judgment

IDENTITY = {"google_sub": "s", "email": "owner@example.test", "youtube_channel_id": "UCowner"}


def prop(channel, action, signals=()):
    return Proposal(channel, action, list(signals), "policy-1", "h-" + channel)


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)
        self.db = store.connect(self.dir / "inventory.sqlite3")
        rows = [{"id": "s" + c, "channel_id": c, "title": t} for c, t in
                (("chanA", "Alpha Labs"), ("chanB", "Beta Beats"), ("chanC", "Gamma Vlog"))]
        with self.db:
            self.db.execute("INSERT INTO sync_runs(id,started_at,status) VALUES (1,'x','running')")
        store.save_inventory(self.db, IDENTITY, rows, 1, 0)

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_latest_label_wins_and_bad_verdict_rejected(self):
        review.label(self.db, "chanA", "keep", "first")
        review.label(self.db, "chanA", "drop", "changed my mind")
        self.assertEqual(review.current_labels(self.db), {"chanA": "drop"})
        with self.assertRaises(ValueError):
            review.label(self.db, "chanA", "maybe", "")

    def test_import_label_file_matches_titles_case_insensitively_and_reports_unmatched(self):
        path = self.dir / "labels.json"
        path.write_text(json.dumps({"keep": ["alpha labs"], "sloppy": ["BETA BEATS", "Ghost Channel"]}))

        result = review.import_label_file(self.db, path)

        self.assertEqual(review.current_labels(self.db), {"chanA": "keep", "chanB": "drop"})
        self.assertEqual(result, {"imported": 2, "unmatched": ["Ghost Channel"]})
        self.assertEqual(review.import_label_file(self.db, path)["imported"], 0)  # re-import adds nothing

    def test_agreement_counts_keep_watch_and_unsubscribe_and_excludes_review_and_unsure(self):
        for c, v in (("chanA", "keep"), ("chanB", "drop"), ("chanC", "keep"), ("chanD", "unsure"), ("chanE", "keep")):
            review.label(self.db, c, v, "")
        proposals = [prop("chanA", "WATCH"), prop("chanB", "KEEP"), prop("chanC", "REVIEW"),
                     prop("chanD", "KEEP"), prop("chanE", "KEEP"), prop("chanF", "KEEP")]

        stats = review.agreement(self.db, proposals)

        # A agrees (WATCH~keep), B disagrees (KEEP vs drop), E agrees; C review, D unsure, F unlabeled excluded
        self.assertEqual(stats, {"n": 3, "agreements": 2, "rate": 2 / 3})

    def test_agreement_can_be_limited_to_held_out_channels(self):
        review.label(self.db, "chanA", "keep", "")
        review.label(self.db, "chanB", "drop", "")
        proposals = [prop("chanA", "KEEP"), prop("chanB", "KEEP")]
        self.assertEqual(review.agreement(self.db, proposals, held_out={"chanB"}), {"n": 1, "agreements": 0, "rate": 0.0})
        self.assertEqual(review.agreement(self.db, [])["rate"], None)

    def test_gate_needs_enough_labels_and_agreement(self):
        gate = lambda n, a: review.gate_status({"n": n, "agreements": a, "rate": a / n if n else None}, PROFILE)
        self.assertEqual(gate(30, 26), {"open": True, "reasons": []})  # 26/30 = 0.867
        few = gate(10, 10)
        self.assertFalse(few["open"])
        self.assertEqual(few["reasons"], ["10 labels, need 30"])
        low = gate(40, 30)  # 0.75
        self.assertFalse(low["open"])
        self.assertEqual(low["reasons"], ["agreement 0.75, need 0.85"])
        self.assertFalse(gate(0, 0)["open"])

    def test_labeling_sample_spans_tiers_and_confidence_and_skips_labeled(self):
        confident = [judgment(val=3.0, val_conf=0.9) for _ in range(4)]
        unsure = [judgment(val=1.0, val_conf=0.2), judgment(val=1.0, val_conf=0.2)]
        judgments = [replace(j, channel_id=f"c{i}") for i, j in enumerate(confident + unsure)]
        review.label(self.db, "c4", "keep", "")  # already labeled: never offered again

        picked = review.sample_for_labeling(self.db, judgments, 2)

        self.assertEqual(picked, ["c5", "c0"])  # one from each stratum, not two confident ones
        self.assertEqual(review.sample_for_labeling(self.db, judgments, 99), ["c5", "c0", "c1", "c2", "c3"])


class ReportTests(unittest.TestCase):
    def test_report_shows_everything_the_owner_needs_in_deterministic_order(self):
        samples = [sample("chanB", "Beta"), sample("chanA", "Alpha")]
        judgments = [replace(judgment(rel=2.5, rel_conf=0.8, val=0.4, pack=0.2, suff=0.9), channel_id="chanB"),
                     replace(judgment(), channel_id="chanA")]
        proposals = [prop("chanA", "KEEP"), prop("chanB", "REVIEW", ["value low (0.4)"])]

        text = review.render_report(proposals, judgments, samples, {"chanA": "keep"})

        self.assertEqual(text, review.render_report(list(reversed(proposals)), judgments, samples, {"chanA": "keep"}))
        self.assertLess(text.index("Beta"), text.index("Alpha"))  # REVIEW before KEEP
        for expected in ("https://www.youtube.com/channel/chanB", "https://www.youtube.com/watch?v=v1",
                         "REVIEW", "value low (0.4)", "relevance: 2.5 (confidence 0.80)",
                         "packaging_risk: 0.20", "evidence_sufficiency: 0.90", "1 of 12 videos",
                         "newest upload 19 days old", "Owner label: keep", "Owner override (keep / drop / unsure): "):
            self.assertIn(expected, text)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)
        db = store.connect(self.dir / "inventory.sqlite3")
        with db:
            db.execute("INSERT INTO sync_runs(id,started_at,status) VALUES (1,'x','running')")
        store.save_inventory(db, IDENTITY, [{"id": "s1", "channel_id": "chanA", "title": "Alpha Labs"}], 1, 0)
        s = sample("chanA", "Alpha Labs", fetched=datetime.now(timezone.utc))
        store.save_samples(db, CollectResult([s], {}), 1)
        # Real judge() path with a fake client, so the cache key is the one propose must find.
        judge(FakeClient(response(relevance=ScoreAnswer(score=0.3, confidence=0.9, legend={0: "a"}, probabilities={0: 1.0}),
                                  apparent_value=ScoreAnswer(score=0.3, confidence=0.9, legend={0: "a"}, probabilities={0: 1.0}))),
              [s], "titles-desc-v1", interests=profile.DEFAULTS["interests"], db=db)
        db.close()

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["--data-dir", str(self.dir), *args])
        return code, out.getvalue()

    def test_propose_label_gate_flow_is_offline(self):
        code, out = self.run_cli("propose")
        self.assertEqual(code, 0)
        self.assertIn("UNSUBSCRIBE", out)
        self.assertIn("Alpha Labs", out)

        self.assertEqual(self.run_cli("label", "chanA", "drop", "--note", "meh")[0], 0)
        code, out = self.run_cli("gate")
        stats = json.loads(out)
        self.assertEqual((stats["n"], stats["agreements"], stats["gate"]["open"]), (1, 1, False))

    def test_propose_marks_trial_channels_using_the_trials_table(self):
        db = store.connect(self.dir / "inventory.sqlite3")
        with db:
            db.execute("INSERT INTO trials VALUES ('chanA', 's1', '2026-09-01T00:00:00+00:00', '2026-10-01T00:00:00+00:00')")
        db.close()

        code, out = self.run_cli("propose")

        self.assertIn("on trial", out)

    def test_labels_import(self):
        path = self.dir / "l.json"
        path.write_text(json.dumps({"keep": ["alpha labs"], "sloppy": []}))
        code, out = self.run_cli("labels", "import", str(path))
        self.assertEqual(json.loads(out), {"imported": 1, "unmatched": []})


if __name__ == "__main__":
    unittest.main()
