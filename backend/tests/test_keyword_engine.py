import unittest
from app.analyzer.keyword_engine import KeywordEngine

ke = KeywordEngine()

JD = """
We are hiring a Backend Developer. You will build REST APIs using Python and FastAPI,
work with PostgreSQL and Docker, and deploy to AWS. Experience with Git and CI/CD is a plus.
Strong communication and teamwork are required. Python is used daily.
"""


class MatchingTests(unittest.TestCase):
    # --- B5: word boundaries ---
    def test_java_does_not_match_javascript(self):
        r = ke.analyze("I use JavaScript every day. Also React and Node.js and TypeScript.",
                       "Looking for Java, Spring Boot and SQL experience.")
        self.assertIn("Java", r["missing_keywords"])
        self.assertNotIn("Java", r["matched_keywords"])

    def test_js_alias_does_not_match_inside_nodejs(self):
        # "Node.js" on a resume must not count as "JavaScript" via the "js" alias
        self.assertFalse(ke._contains("Built services with Node.js", "JavaScript"))
        self.assertTrue(ke._contains("Wrote JS and TS code", "JavaScript"))

    def test_symbols_terms(self):
        self.assertTrue(ke._contains("Experienced in C++ and C#.", "C++"))
        self.assertTrue(ke._contains("Experienced in C++ and C#.", "C#"))
        self.assertTrue(ke._contains("Built apps on .NET 8", ".NET"))
        self.assertTrue(ke._contains("Set up CI/CD pipelines", "CI/CD"))

    def test_aliases_count_as_match(self):
        self.assertTrue(ke._contains("Deployed on k8s clusters", "Kubernetes"))
        self.assertTrue(ke._contains("Used Postgres and psql", "PostgreSQL"))
        self.assertTrue(ke._contains("continuous integration", "CI/CD"))

    def test_case_sensitive_everyday_words(self):
        self.assertFalse(ke._contains("I excel at teamwork", "Excel"))
        self.assertTrue(ke._contains("Advanced Excel formulas", "Excel"))

    def test_no_ambiguous_rest_or_spring(self):
        self.assertFalse(ke._contains("Joined in Spring 2024 and did the rest", "REST API"))
        self.assertFalse(ke._contains("Joined in Spring 2024", "Spring Boot"))


class ExtractionTests(unittest.TestCase):
    # --- B3 / B4 ---
    def test_deterministic(self):
        runs = [ke._extract_skills(JD) for _ in range(5)]
        self.assertTrue(all(r == runs[0] for r in runs))

    def test_ranked_by_frequency_python_first(self):
        skills = ke._extract_skills(JD)
        self.assertEqual(skills[0][0], "Python")   # mentioned twice

    def test_no_junk_phrases(self):
        names = [n.lower() for n, _ in ke._extract_skills(JD)]
        for junk in ("the team", "our company", "you", "we"):
            self.assertNotIn(junk, names)

    def test_hyphen_and_space_variants_are_one_skill(self):
        names = [n for n, _ in ke._extract_skills("Strong problem solving and problem-solving skills")]
        self.assertEqual(names.count("Problem Solving"), 1)
        self.assertNotIn("Problem-Solving", names)

    def test_extracts_expected_skills(self):
        names = {n for n, _ in ke._extract_skills(JD)}
        for expected in ("Python", "FastAPI", "PostgreSQL", "Docker", "AWS", "Git", "CI/CD",
                         "REST API", "Communication", "Teamwork"):
            self.assertIn(expected, names)

    def test_junior_job_soft_skill_groups_are_canonical(self):
        jd = (
            "You're a team player who loves contributing ideas and collaborating with others. "
            "You have good communication skills and are comfortable coordinating with clients. "
            "You're committed to continuous learning and professional growth. "
            "You may be asked to teach classes or maintain training materials."
        )
        names = [name for name, _ in ke._extract_skills(jd)]
        for expected in ("Teamwork", "Communication", "Continuous Learning", "Client Coordination", "Knowledge Sharing"):
            self.assertIn(expected, names)
        self.assertEqual(len(names), len(set(names)))
        self.assertNotIn("Team Player", names)

        result = ke.analyze(
            "Collaborative team settings. Led a 5-member team. Full Stack Developer.",
            jd,
        )
        self.assertTrue(result["score_available"])
        self.assertIn("Teamwork", result["matched_keywords"])


class ScoreTests(unittest.TestCase):
    def test_score_math(self):
        resume = "Built REST APIs in Python with FastAPI and PostgreSQL. Used Docker, AWS, Git."
        r = ke.analyze(resume, JD)
        self.assertTrue(r["score_available"])
        self.assertIn("Python", r["matched_keywords"])
        self.assertIn("Communication", r["missing_keywords"])
        expected = round(len(r["matched_keywords"]) / r["total_jd_keywords"] * 100, 1)
        self.assertEqual(r["score"], expected)

    def test_jd_with_too_few_skills_has_no_score(self):
        r = ke.analyze("Some resume text", "We want a friendly person who likes cats.")
        self.assertIsNone(r["score"])
        self.assertFalse(r["score_available"])
        self.assertTrue(r["reason"])

    def test_empty_jd(self):
        r = ke.analyze("Python developer", "")
        self.assertIsNone(r["score"])


class SoftSkillSeparationTests(unittest.TestCase):
    """A3: soft skills are advice only — never added to the skills section."""

    def test_soft_missing_keywords_are_flagged_separately(self):
        r = ke.analyze("Backend developer using Python.", JD)
        # still counted in the keyword score/missing list...
        self.assertIn("Communication", r["missing_keywords"])
        # ...but flagged so the UI can steer them to bullets instead
        self.assertIn("Communication", r["soft_missing_keywords"])
        self.assertIn("Teamwork", r["soft_missing_keywords"])
        self.assertNotIn("Docker", r["soft_missing_keywords"])
        self.assertIn("Docker", r["missing_keywords"])


class SkillCategoryTests(unittest.TestCase):
    """A3: confirmed keywords fold into the matching labeled skills line."""

    def test_every_hard_skill_has_exactly_one_category(self):
        from app.common.skills import HARD_SKILLS, HARD_SKILL_CATEGORIES

        mapped = [name for names in HARD_SKILL_CATEGORIES.values() for name in names]
        self.assertEqual(len(mapped), len(set(mapped)), "duplicate category entry")
        self.assertEqual(set(mapped), set(HARD_SKILLS))

    def test_resume_labels_match_their_categories(self):
        from app.common.skills import label_matches_category

        self.assertTrue(label_matches_category("Databases", "Databases"))
        self.assertTrue(label_matches_category("APIs & ORMs", "Backend"))
        self.assertTrue(label_matches_category("DevOps & Tools", "Cloud & DevOps"))
        self.assertTrue(label_matches_category("DevOps & Tools", "Process & Tools"))
        self.assertFalse(label_matches_category("Languages", "Databases"))

    def test_paradigms_do_not_match_a_tools_label(self):
        # Caught live: OOP was filed under "DevOps & Tools" because the
        # Process & Tools label keywords contained the generic word "tools".
        from app.common.skills import label_matches_category, skill_category

        self.assertEqual(skill_category("Object-Oriented Programming"), "Concepts")
        self.assertEqual(skill_category("Design Patterns"), "Concepts")
        self.assertFalse(label_matches_category("DevOps & Tools", "Concepts"))
        self.assertFalse(label_matches_category("Languages", "Concepts"))

    def test_actual_tools_still_match_a_tools_label(self):
        from app.common.skills import label_matches_category, skill_category

        self.assertEqual(skill_category("Figma"), "Process & Tools")
        self.assertEqual(skill_category("Jira"), "Process & Tools")
        self.assertTrue(label_matches_category("DevOps & Tools", "Process & Tools"))
        # ...and the label is still recognised as cloud/devops for real skills
        self.assertTrue(label_matches_category("DevOps & Tools", "Cloud & DevOps"))


if __name__ == "__main__":
    unittest.main()
