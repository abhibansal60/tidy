import json
from pathlib import Path
import tempfile
import unittest

from evals import label_retest


class LabelRetestTests(unittest.TestCase):
    def run_retest(self, current, blind):
        with tempfile.TemporaryDirectory() as d:
            sheet, mapping = Path(d) / "sheet.json", Path(d) / "map.json"
            sheet.write_text(json.dumps({"channels": [{"n": i + 1, "title": "t", "verdict": v} for i, v in enumerate(blind)]}))
            mapping.write_text(json.dumps({str(i + 1): f"c{i}" for i in range(len(blind))}))
            return label_retest.retest({f"c{i}": v for i, v in enumerate(current)}, sheet, mapping)

    def test_agreement_kappa_and_noise_ceiling_ignore_unsure_and_blank(self):
        # 10 comparable pairs: 8 agree; one unsure and one blank are skipped
        current = ["keep"] * 5 + ["drop"] * 5 + ["keep", "drop"]
        blind = ["keep", "keep", "keep", "keep", "drop", "drop", "drop", "drop", "keep", "keep", "unsure", ""]
        out = self.run_retest(current, blind)

        self.assertEqual((out["compared"], out["agreed"]), (10, 7))
        self.assertAlmostEqual(out["agreement"], 0.7)
        self.assertAlmostEqual(out["kappa"], 0.4, places=2)  # observed .7, expected .5 -> (.7-.5)/(1-.5)
        self.assertEqual(out["skipped"], 2)
        self.assertAlmostEqual(out["ceiling"], 1 - (1 - 0.4 ** 0.5) / 2, places=2)

    def test_perfect_agreement_gives_a_ceiling_of_one(self):
        out = self.run_retest(["keep", "drop", "drop"], ["keep", "drop", "drop"])
        self.assertEqual((out["agreement"], out["ceiling"]), (1.0, 1.0))


if __name__ == "__main__":
    unittest.main()
