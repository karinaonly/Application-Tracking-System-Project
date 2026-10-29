import unittest
from app.analyzer.scoring import SCORE_WEIGHTS, compute_overall


class OverallScoreTests(unittest.TestCase):
    # --- B1 ---
    def test_all_components(self):
        overall, w = compute_overall(
            {"ats": 80, "bullets": 60, "keywords": 50, "grammar": 100}
        )
        self.assertEqual(overall, 67.0)  # 80*.30 + 60*.30 + 50*.30 + 100*.10
        self.assertAlmostEqual(sum(w.values()), 1.0, places=2)

    # --- B10 ---
    def test_weights_sum_to_one(self):
        self.assertAlmostEqual(sum(SCORE_WEIGHTS.values()), 1.0, places=6)

    def test_grammar_is_part_of_the_overall_score(self):
        # B10: grammar used to be computed and thrown away.
        without_grammar, _ = compute_overall(
            {"ats": 100, "bullets": 100, "keywords": 100, "grammar": None}
        )
        with_grammar, _ = compute_overall(
            {"ats": 100, "bullets": 100, "keywords": 100, "grammar": 0}
        )
        self.assertEqual(without_grammar, 100.0)
        self.assertEqual(with_grammar, 90.0)
        self.assertLess(with_grammar, without_grammar)

    def test_grammar_only_is_available(self):
        overall, w = compute_overall(
            {"ats": None, "bullets": None, "keywords": None, "grammar": 60}
        )
        self.assertEqual(overall, 60.0)
        self.assertEqual(w, {"grammar": 1.0})

    def test_no_job_description_is_not_treated_as_100(self):
        overall, w = compute_overall(
            {"ats": 80, "bullets": 60, "keywords": None, "grammar": 100}
        )
        self.assertEqual(overall, 74.3)  # (80*.30 + 60*.30 + 100*.10) / .70
        self.assertNotIn("keywords", w)
        self.assertAlmostEqual(sum(w.values()), 1.0, places=2)

    def test_old_behavior_would_have_inflated(self):
        # old: 80*.35 + 60*.35 + 100*.30 = 79.0  (fake boost from a phantom 100)
        overall, _ = compute_overall(
            {"ats": 80, "bullets": 60, "keywords": None, "grammar": 100}
        )
        self.assertLess(overall, 79.0)

    def test_no_bullets_dropped(self):
        overall, w = compute_overall(
            {"ats": 80, "bullets": None, "keywords": 40, "grammar": 100}
        )
        self.assertNotIn("bullets", w)
        self.assertAlmostEqual(overall, (80 * .30 + 40 * .30 + 100 * .10) / .70, places=1)

    def test_grammar_unavailable_is_dropped(self):
        overall, w = compute_overall(
            {"ats": 80, "bullets": 60, "keywords": 50, "grammar": None}
        )
        self.assertNotIn("grammar", w)
        self.assertAlmostEqual(overall, (80 * .30 + 60 * .30 + 50 * .30) / .90, places=1)

    def test_nothing_available(self):
        self.assertEqual(
            compute_overall({"ats": None, "bullets": None, "keywords": None, "grammar": None}),
            (0.0, {}),
        )


if __name__ == "__main__":
    unittest.main()
