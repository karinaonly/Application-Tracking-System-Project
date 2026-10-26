import unittest
from app.analyzer.bullet_analyzer import BulletAnalyzer

ba = BulletAnalyzer()


def vt(text):
    return ba._check_bullet(text, "Experience")["verb_type"]


class WeakVerbTests(unittest.TestCase):
    # --- A1: these used to be wrongly flagged "weak" by substring matching ---
    def test_no_false_positive_did(self):
        self.assertNotEqual(vt("Candidate screening tool for HR"), "weak")

    def test_no_false_positive_had(self):
        self.assertNotEqual(vt("Shadow mode rollout of new service"), "weak")

    def test_no_false_positive_made(self):
        self.assertNotEqual(vt("Mademoiselle checkout flow"), "weak")

    def test_weak_word_not_at_start_is_ignored(self):
        self.assertNotEqual(vt("Built pipeline; assisted by two interns"), "weak")

    # --- real weak bullets must still be caught ---
    def test_real_weak_single_word(self):
        self.assertEqual(vt("Helped the team migrate services"), "weak")
        self.assertEqual(vt("Assisted with customer onboarding"), "weak")

    def test_real_weak_phrases(self):
        self.assertEqual(vt("Responsible for maintaining the API"), "weak")
        self.assertEqual(vt("Was responsible for daily reports"), "weak")
        self.assertEqual(vt("Worked on the billing module"), "weak")

    def test_bullet_marker_is_ignored(self):
        self.assertEqual(vt("• Helped the team migrate services"), "weak")
        self.assertEqual(vt("- Developed REST APIs"), "strong")

    def test_strong_verb(self):
        self.assertEqual(vt("Developed REST APIs with FastAPI"), "strong")

    def test_suggestion_uses_matched_phrase(self):
        r = ba._check_bullet("Responsible for the API", "Experience")
        self.assertIn("Managed", r["suggestion"])


class NoBulletsTests(unittest.TestCase):
    # --- B2 ---
    def test_zero_bullets_is_not_a_perfect_score(self):
        r = ba.analyze_bullets([])
        self.assertIsNone(r["score"])
        self.assertFalse(r["score_available"])
        self.assertTrue(r["warning"])

    def test_entries_without_bullets(self):
        r = ba.analyze_bullets([{"bullets": []}, {}])
        self.assertIsNone(r["score"])

    def test_normal_score_still_computed(self):
        r = ba.analyze_bullets([{"bullets": ["Reduced load time by 40%", "Helped with stuff"]}])
        self.assertTrue(r["score_available"])
        # 1/2 with metrics, 1/2 strong verbs -> 25 + 25
        self.assertEqual(r["score"], 50.0)


class MetricTests(unittest.TestCase):
    def test_small_quantity_numbers_count_as_metrics(self):
        for text in (
            "Led a 5-member team to build a payroll system",
            "Collaborated with a 5-member team to assemble the hardware",
            "Built 3 REST endpoints",
        ):
            self.assertTrue(ba._check_bullet(text, "Experience")["has_metrics"], text)

    def test_metric_formats_count(self):
        for text in (
            "Reduced load time by 40%",
            "Saved ₱50,000 monthly",
            "Serving 10k users",
            "Cut merge conflicts by 3x",
            "Processed 1,200 records",
            "Improved speed by 12.5%",
        ):
            self.assertTrue(ba._check_bullet(text, "Experience")["has_metrics"], text)

    def test_versions_and_years_do_not_count(self):
        for text in (
            "Built API with Python 3.11",
            "Used HTML5 and CSS3",
            "Developed in 2024",
            "Worked 2025 - 2026",
            "Built with ES6 and OAuth2",
            "Deployed on EC2 and S3",
            "Migrated to Next.js 14",
            "Upgraded to Node 18",
        ):
            self.assertFalse(ba._check_bullet(text, "Experience")["has_metrics"], text)


if __name__ == "__main__":
    unittest.main()
