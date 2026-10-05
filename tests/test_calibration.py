import unittest

from evals import calibration as cal


class CalibrationMetricTests(unittest.TestCase):
    def test_reliability_bins_and_ece(self):
        conf = [0.95, 0.95, 0.95, 0.95, 0.55, 0.55]
        correct = [True, True, True, False, True, False]
        bins = cal.reliability(conf, correct, bins=10)

        self.assertEqual([(b["n"], b["accuracy"]) for b in bins], [(2, 0.5), (4, 0.75)])
        # |0.5-0.55|*2/6 + |0.75-0.95|*4/6
        self.assertAlmostEqual(cal.ece(conf, correct), 0.05 * 2 / 6 + 0.2 * 4 / 6)

    def test_confidence_of_one_lands_in_the_top_bin(self):
        self.assertEqual(cal.reliability([1.0], [True])[0]["lo"], 0.9)

    def test_brier_and_auroc(self):
        self.assertAlmostEqual(cal.brier([1.0, 0.0, 0.5], [True, False, True]), 0.25 / 3)
        self.assertEqual(cal.auroc([0.9, 0.8, 0.1], [True, True, False]), 1.0)
        self.assertEqual(cal.auroc([0.5, 0.5], [True, False]), 0.5)
        self.assertIsNone(cal.auroc([0.9], [True]))  # undefined without a false item
        self.assertEqual(cal.auroc_ci([0.9], [True]), (None, None))

    def test_abstain_table_reports_coverage_and_error_among_answered(self):
        conf = [0.9, 0.8, 0.7, 0.4]
        correct = [True, True, False, False]
        rows = {r["threshold"]: r for r in cal.abstain_table(conf, correct, [0.5, 0.75, 0.95])}

        self.assertEqual(rows[0.5]["coverage"], 0.75)
        self.assertAlmostEqual(rows[0.5]["error"], 1 / 3)
        self.assertEqual((rows[0.75]["coverage"], rows[0.75]["error"]), (0.5, 0.0))
        self.assertEqual((rows[0.95]["coverage"], rows[0.95]["error"]), (0.0, None))

    def test_heldout_gate_picks_threshold_on_half_a_and_scores_half_b(self):
        # half A: errors only below 0.6, so the lowest threshold with error <= 5% is 0.6
        conf = [0.9, 0.7, 0.6, 0.5, 0.9, 0.7, 0.6, 0.4]
        correct = [True, True, True, False, True, False, True, False]
        half_a = [True] * 4 + [False] * 4
        gate = cal.heldout_gate(conf, correct, half_a, max_error=0.05)

        self.assertEqual(gate["threshold"], 0.6)
        self.assertEqual(gate["b_coverage"], 0.75)
        self.assertAlmostEqual(gate["b_error"], 1 / 3)

    def test_risk_coverage_answers_most_confident_first_and_keeps_ties_together(self):
        curve = cal.risk_coverage([0.9, 0.5, 0.9, 0.2], [True, False, False, True])
        self.assertEqual(curve, [(0.5, 0.5), (0.75, 2 / 3), (1.0, 0.5)])

    def test_bootstrap_interval_brackets_the_estimate(self):
        correct = [True] * 80 + [False] * 20
        lo, hi = cal.bootstrap(correct, cal.accuracy)
        self.assertLess(lo, 0.8)
        self.assertGreater(hi, 0.8)
        self.assertEqual(cal.bootstrap(correct, cal.accuracy), (lo, hi))  # seeded

    def test_repeatability(self):
        a = {"x": ("bug", 0.9), "y": ("feature", 0.5)}
        b = {"x": ("bug", 0.8), "y": ("question", 0.5), "z": ("bug", 1.0)}
        self.assertEqual(cal.repeatability(a, b), {"items": 2, "label_agreement": 0.5, "mean_abs_change": 0.05})


if __name__ == "__main__":
    unittest.main()
