import unittest

from app.jobs.parser import JobParser

# Anonymized but realistic two-section JD
JD_TEXT = """Senior Backend Developer at Acme Corp

About the role
We are building a payment platform serving 2 million users.

Requirements:
- 5+ years of experience with Python and Django
- Strong experience with PostgreSQL and Redis
- Experience with Docker and AWS
- Solid understanding of REST API design

Nice to have:
- Kubernetes and Terraform experience is a plus
- Familiarity with GraphQL
- Knowledge of Kafka

Benefits
We offer competitive pay and a learning budget.
"""


class JobParserTests(unittest.TestCase):
    """D2: the JD parser extracts required/preferred skills, tools, seniority."""

    def setUp(self):
        self.parser = JobParser()

    def test_required_and_preferred_are_split_by_section(self):
        out = self.parser.parse(JD_TEXT, "Senior Backend Developer")
        self.assertIn("Python", out["required_skills"])
        self.assertIn("Django", out["required_skills"])
        self.assertIn("PostgreSQL", out["required_skills"])
        self.assertIn("REST API", out["required_skills"])
        # "Nice to have" section
        self.assertIn("Kubernetes", out["preferred_skills"])
        self.assertIn("GraphQL", out["preferred_skills"])
        self.assertIn("Kafka", out["preferred_skills"])
        # required skills must not leak into preferred and vice versa
        self.assertNotIn("Python", out["preferred_skills"])
        self.assertNotIn("Kubernetes", out["required_skills"])

    def test_skills_mentioned_outside_sections_land_in_other(self):
        out = self.parser.parse(JD_TEXT, "Senior Backend Developer")
        # "payment platform" isn't in the taxonomy; but a skill named in the
        # intro ("About the role") lands in "other"
        self.assertNotIn("Python", out["other_skills"])

    def test_tools_are_extracted_from_parsed_skills(self):
        out = self.parser.parse(JD_TEXT, "Senior Backend Developer")
        self.assertIn("Docker", out["tools"])
        self.assertIn("AWS", out["tools"])
        self.assertIn("Redis", out["tools"])
        # languages/frameworks are not tools
        self.assertNotIn("Python", out["tools"])
        self.assertNotIn("Django", out["tools"])

    def test_seniority_from_title(self):
        self.assertEqual(self.parser.parse(JD_TEXT, "Senior Backend Developer")["seniority"], "senior")
        self.assertEqual(self.parser.parse("text", "Junior Dev")["seniority"], "junior")
        self.assertEqual(self.parser.parse("text", "Internship Program")["seniority"], "intern")
        self.assertEqual(self.parser.parse("no signals here", "Developer")["seniority"], "unspecified")

    def test_seniority_falls_back_to_body(self):
        body = "We are hiring for our platform team.\nThis is an entry-level position with mentoring."
        self.assertEqual(self.parser.parse(body, "Developer")["seniority"], "junior")

    def test_min_years_experience(self):
        self.assertEqual(self.parser.parse(JD_TEXT, "Senior Backend Developer")["min_years_experience"], 5)
        self.assertEqual(self.parser.parse("2+ years of experience required", "Dev")["min_years_experience"], 2)
        self.assertIsNone(self.parser.parse("no experience mention", "Dev")["min_years_experience"])
        # absurd numbers are rejected
        self.assertIsNone(self.parser.parse("100 years of experience", "Dev")["min_years_experience"])

    def test_jd_without_sections_still_finds_skills(self):
        body = "You will build Python microservices with Docker and PostgreSQL."
        out = self.parser.parse(body, "Backend Developer")
        self.assertIn("Python", out["other_skills"])
        self.assertIn("Docker", out["other_skills"])
        self.assertEqual(out["required_skills"], [])
        self.assertIn("Docker", out["tools"])

    def test_empty_text_is_safe(self):
        out = self.parser.parse("", "")
        self.assertEqual(out["required_skills"], [])
        self.assertEqual(out["preferred_skills"], [])
        self.assertEqual(out["other_skills"], [])
        self.assertEqual(out["tools"], [])
        self.assertEqual(out["seniority"], "unspecified")
        self.assertIsNone(out["min_years_experience"])

    def test_inline_requirements_header_mid_line(self):
        body = "Role overview here.\nRequirements: Python, Docker, and 3+ years of experience.\nPreferred: Kubernetes."
        out = self.parser.parse(body, "Developer")
        self.assertIn("Python", out["required_skills"])
        self.assertIn("Kubernetes", out["preferred_skills"])
        self.assertEqual(out["min_years_experience"], 3)


if __name__ == "__main__":
    unittest.main()
