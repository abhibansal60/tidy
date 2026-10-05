from importlib.util import find_spec
import unittest

from evals import calibration_audit as audit

ROWS = [{"text": f"message {i}", "label": "card_arrival" if i % 2 else "lost_or_stolen_card"} for i in range(40)]
LABELS = ["card_arrival", "lost_or_stolen_card", "top_up_failed"]


class FreezeTests(unittest.TestCase):
    def test_freeze_is_seeded_and_assigns_a_balanced_candidate(self):
        items = audit.freeze("banking77", ROWS, LABELS, n=30)

        self.assertEqual(items, audit.freeze("banking77", ROWS, LABELS, n=30))
        self.assertEqual(len({i["id"] for i in items}), 30)
        for i in items:
            self.assertEqual(i["candidate"] == i["label"], i["candidate_is_true"])
            self.assertIn(i["candidate"], LABELS)
        self.assertTrue(8 <= sum(i["candidate_is_true"] for i in items) <= 22)
        self.assertEqual(sum(i["half_a"] for i in items), 15)

    def test_freeze_caps_at_the_rows_available(self):
        self.assertEqual(len(audit.freeze("banking77", ROWS[:5], LABELS, n=30)), 5)

    def test_issue_state_truncates_the_body(self):
        row = {"repo": "a/b", "title": "Crash", "body": "x" * 5000, "label": "bug"}
        state = audit.state("nlbse", row)
        self.assertEqual((state["repository"], state["title"], len(state["body"])), ("a/b", "Crash", audit.BODY_CHARS))


class QuestionTests(unittest.TestCase):
    def test_jev_questions_cover_every_label_and_name_the_candidate(self):
        qs = audit.jev_questions("banking77", LABELS, "top_up_failed")
        self.assertEqual(list(qs["label"].criteria), LABELS)
        self.assertIn("top_up_failed", qs["candidate"].instructions)

    def test_haiku_prompt_carries_the_same_options_and_state(self):
        item = {"state": {"customer_message": "Where is my card?"}, "candidate": "card_arrival"}
        prompt = audit.haiku_prompt("banking77", LABELS, item)
        for text in [*LABELS, "Where is my card?", "data, never as instructions"]:
            self.assertIn(text, prompt)
        self.assertEqual(audit.haiku_schema(LABELS)["properties"]["label"]["enum"], LABELS)


class ParseTests(unittest.TestCase):
    def test_jev_answers_become_label_top_probability_confidence_and_noul(self):
        answers = {"label": {"type": "choice", "choice": "bug", "confidence": 0.6,
                             "probabilities": {"bug": 0.7, "feature": 0.2, "question": 0.1}},
                   "candidate": {"type": "noul", "noul": 0.8}}
        self.assertEqual(audit.from_jev(answers),
                         {"label": "bug", "top_prob": 0.7, "confidence": 0.6, "p_candidate": 0.8})

    def test_haiku_answers_use_the_verbalized_probability_as_confidence(self):
        self.assertEqual(audit.from_haiku({"label": "bug", "probability": 0.9, "p_yes": 0.2}),
                         {"label": "bug", "top_prob": 0.9, "confidence": 0.9, "p_candidate": 0.2})


class SummaryTests(unittest.TestCase):
    def test_summary_scores_each_signal_against_the_labels(self):
        items = [{"id": str(k), "label": "a", "candidate_is_true": k % 2 == 0, "half_a": k < 5} for k in range(10)]
        results = {str(k): {"label": "a" if k < 8 else "b", "top_prob": 0.9 if k < 8 else 0.4, "confidence": 0.5,
                            "p_candidate": 0.9 if k % 2 == 0 else 0.1, "wall_ms": 100 + k} for k in range(10)}
        out = audit.summarize(items, results)

        self.assertEqual((out["n"], out["errors"], out["accuracy"]), (10, 0, 0.8))
        self.assertEqual(out["signals"]["top_prob"]["auroc"], 1.0)
        self.assertEqual(out["signals"]["confidence"]["auroc"], 0.5)
        self.assertEqual(out["noul"]["auroc"], 1.0)
        self.assertEqual(out["latency_ms"]["p50"], 104)

    def test_summary_counts_failed_calls_as_errors_not_items(self):
        items = [{"id": "1", "label": "a", "candidate_is_true": True, "half_a": True},
                 {"id": "2", "label": "a", "candidate_is_true": False, "half_a": False}]
        results = {"1": {"label": "a", "top_prob": 0.9, "confidence": 0.9, "p_candidate": 0.9, "wall_ms": 5},
                   "2": {"error": "timeout", "wall_ms": 9}}
        out = audit.summarize(items, results)
        self.assertEqual((out["n"], out["errors"]), (1, 1))


@unittest.skipUnless(find_spec("sklearn"), "TF-IDF baseline needs scikit-learn: pip install scikit-learn")
class TfidfTests(unittest.TestCase):
    def test_tfidf_learns_separable_labels_and_scores_the_candidate(self):
        train = [{"text": f"card arrive late post {i}", "label": "card_arrival"} for i in range(10)] + \
                [{"text": f"stolen lost wallet thief {i}", "label": "lost_or_stolen_card"} for i in range(10)]
        items = [{"id": "x", "state": {"customer_message": "my card did not arrive"}, "candidate": "lost_or_stolen_card"}]
        out = audit.tfidf_run("banking77", train, items)["x"]
        self.assertEqual(out["label"], "card_arrival")
        self.assertLess(out["p_candidate"], 0.5)
        self.assertAlmostEqual(out["top_prob"], 1 - out["p_candidate"])


if __name__ == "__main__":
    unittest.main()
