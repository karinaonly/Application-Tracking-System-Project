import unittest
from app.analyzer.scoring import compute_overall


class OverallScoreTests(unittest.TestCase):
    # --- B1 ---
    def test_all_components(self):
        overall, w = compute_overall({"ats": 80, "bullets": 60, "keywords": 50})
        self.assertEqual(overall, round(80 * .35 + 60 * .35 + 50 * .30, 1))
        self.assertAlmostEqual(sum(w.values()), 1.0, places=2)

    def test_no_job_description_is_not_treated_as_100(self):
        overall, w = compute_overall({"ats": 80, "bullets": 60, "keywords": None})
        self.assertEqual(overall, 70.0)           # avg of 80 and 60 (equal weights)
        self.assertNotIn("keywords", w)

    def test_old_behavior_would_have_inflated(self):
        # old: 80*.35 + 60*.35 + 100*.30 = 79.0  (fake boost from a phantom 100)
        overall, _ = compute_overall({"ats": 80, "bullets": 60, "keywords": None})
        self.assertLess(overall, 79.0)

    def test_no_bullets_dropped(self):
        overall, w = compute_overall({"ats": 80, "bullets": None, "keywords": 40})
        self.assertNotIn("bullets", w)
        self.assertAlmostEqual(overall, (80 * .35 + 40 * .30) / .65, places=1)

    def test_nothing_available(self):
        self.assertEqual(compute_overall({"ats": None, "bullets": None, "keywords": None}), (0.0, {}))


if __name__ == "__main__":
    unittest.main()
