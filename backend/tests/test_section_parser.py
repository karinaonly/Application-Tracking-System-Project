import unittest
from pathlib import Path

from app.parser.section_parser import SectionParser

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class ContactParsingTests(unittest.TestCase):
    """A15: contact lines are parsed field-by-field."""

    def setUp(self):
        self.parser = SectionParser()

    def test_contact_fields(self):
        contact = self.parser._parse_contact(
            "Jane Anne Santos-Dela Cruz\n"
            "Quezon City, Metro Manila 1108\n"
            "jane.santos@email.com | +63 917 123 4567\n"
            "linkedin.com/in/jane-santos\n"
            "github.com/janesantos\n"
            "https://janesantos.dev"
        )
        self.assertEqual(contact["name"], "Jane Anne Santos-Dela Cruz")
        self.assertEqual(contact["email"], "jane.santos@email.com")
        self.assertEqual(contact["phone"], "+63 917 123 4567")
        self.assertEqual(contact["linkedin"], "linkedin.com/in/jane-santos")
        self.assertEqual(contact["github"], "github.com/janesantos")
        self.assertEqual(contact["portfolio"], "https://janesantos.dev")
        self.assertEqual(contact["location"], "Quezon City, Metro Manila 1108")

    def test_line_with_email_is_never_the_name(self):
        contact = self.parser._parse_contact("Jane Santos jane.santos@email.com")
        self.assertEqual(contact["email"], "jane.santos@email.com")
        self.assertNotIn("@", contact["name"])

    def test_line_with_phone_is_never_the_name(self):
        contact = self.parser._parse_contact("+63 917 123 4567 Jane Santos")
        self.assertEqual(contact["phone"], "+63 917 123 4567")
        self.assertNotIn("917", contact["name"])

    def test_labeled_linkedin_parses(self):
        contact = self.parser._parse_contact("Maria Cruz\nLinkedIn: linkedin.com/in/maria-cruz")
        self.assertEqual(contact["linkedin"], "linkedin.com/in/maria-cruz")
        self.assertEqual(contact["name"], "Maria Cruz")

    def test_labeled_bare_username_normalized(self):
        contact = self.parser._parse_contact("Maria Cruz\nLinkedIn: maria-cruz\nGitHub: mariacruz")
        self.assertEqual(contact["linkedin"], "linkedin.com/in/maria-cruz")
        self.assertEqual(contact["github"], "github.com/mariacruz")

    def test_linkedin_and_github_never_leak_into_portfolio(self):
        contact = self.parser._parse_contact(
            "Maria Cruz\nhttps://linkedin.com/in/maria-cruz\nhttps://github.com/mariacruz\nhttps://mariacruz.dev"
        )
        self.assertEqual(contact["portfolio"], "https://mariacruz.dev")
        self.assertIn("linkedin.com", contact["linkedin"])
        self.assertIn("github.com", contact["github"])

    def test_location_does_not_swallow_name(self):
        contact = self.parser._parse_contact(
            "Jane Anne Santos-Dela Cruz\nQuezon City, Metro Manila 1108"
        )
        self.assertEqual(contact["name"], "Jane Anne Santos-Dela Cruz")
        self.assertEqual(contact["location"], "Quezon City, Metro Manila 1108")


class InlineHeaderTests(unittest.TestCase):
    """A15: inline section headers like 'Skills: Python, React'."""

    def setUp(self):
        self.parser = SectionParser()

    def test_inline_skills_header(self):
        sections = self.parser.parse("SKILLS: Python, JavaScript, React")
        self.assertIn("skills", sections["_section_order"])
        self.assertEqual(sections["skills_parsed"], ["Python", "JavaScript", "React"])

    def test_inline_mixed_case_header(self):
        sections = self.parser.parse("Summary: Backend developer with 3 years of experience.")
        self.assertIn("summary", sections["_section_order"])
        self.assertIn("Backend developer", sections["summary"]["raw"])

    def test_normal_lines_are_not_inline_headers(self):
        sections = self.parser.parse("EXPERIENCE\nBuilt REST APIs with Python and JavaScript")
        self.assertEqual(sections["_section_order"], ["experience"])
        self.assertNotIn("skills", sections["_section_order"])

    def test_skills_section_still_detected_standalone(self):
        sections = self.parser.parse("SKILLS\nPython, JavaScript, React")
        self.assertIn("skills", sections["_section_order"])
        self.assertEqual(sections["skills_parsed"], ["Python", "JavaScript", "React"])


class EducationParsingTests(unittest.TestCase):
    """A15: school extraction is anchored on the degree line."""

    def setUp(self):
        self.parser = SectionParser()

    def test_school_name_with_university_is_preserved(self):
        entries = self.parser._parse_education("University of the Philippines\nB.S. Computer Science, 2024")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["school"], "University of the Philippines")
        self.assertEqual(entries[0]["degree"], "B.S. Computer Science")
        self.assertEqual(entries[0]["dates"], "2024")

    def test_degree_first_layout(self):
        entries = self.parser._parse_education("B.S. Computer Science\nUniversity of the Philippines\n2020 - 2024")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["degree"], "B.S. Computer Science")
        self.assertEqual(entries[0]["school"], "University of the Philippines")
        self.assertEqual(entries[0]["dates"], "2020 - 2024")

    def test_separate_entries_are_kept(self):
        entries = self.parser._parse_education(
            "University of the Philippines\nB.S. Computer Science, 2024\n"
            "University of Santo Tomas\nM.S. Data Science, 2026"
        )
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["school"], "University of the Philippines")
        self.assertEqual(entries[1]["school"], "University of Santo Tomas")
        self.assertEqual(entries[1]["degree"], "M.S. Data Science")

    def test_master_layout_label_prefix_still_stripped(self):
        self.assertEqual(self.parser._clean_degree("School, ABM Strand"), "ABM Strand")
        self.assertEqual(self.parser._clean_degree("Senior High School — ABM Strand"), "ABM Strand")
        self.assertEqual(self.parser._clean_degree("College"), "")


class FixtureTests(unittest.TestCase):
    """F4 (partial): anonymized sample resumes as parser fixtures."""

    def setUp(self):
        self.parser = SectionParser()

    def test_classic_fixture(self):
        sections = self.parser.parse(load_fixture("resume_classic.txt"))
        order = sections["_section_order"]
        for expected in ("summary", "experience", "projects", "skills", "education", "certifications", "languages"):
            self.assertIn(expected, order, f"missing section: {expected}")
        self.assertNotIn("references", order)

        contact = sections["contact_parsed"]
        self.assertEqual(contact["name"], "JANE ANNE SANTOS-DELA CRUZ")
        self.assertEqual(contact["email"], "jane.santos@email.com")
        self.assertEqual(contact["linkedin"], "linkedin.com/in/jane-santos")
        self.assertEqual(contact["portfolio"], "https://janesantos.dev")

        skills = sections["skills_parsed"]
        self.assertIn("Python", skills)
        self.assertIn("React", skills)
        self.assertFalse(any("SKILLS" in s for s in skills))

        experience = sections["experience_parsed"]
        self.assertEqual(len(experience), 2)
        self.assertEqual(experience[0]["title"], "Software Engineer")
        self.assertEqual(experience[0]["company"], "Acme Corp")
        self.assertEqual(len(experience[0]["bullets"]), 2)

        education = sections["education_parsed"]
        self.assertEqual(len(education), 1)
        self.assertEqual(education[0]["school"], "University of the Philippines")
        self.assertEqual(education[0]["degree"], "B.S. Computer Science, Cum Laude")
        self.assertEqual(education[0]["dates"], "2020 - 2024")

    def test_master_layout_fixture(self):
        sections = self.parser.parse(load_fixture("resume_master_layout.txt"))
        experience = sections["experience_parsed"]
        self.assertEqual(len(experience), 3)
        self.assertEqual(experience[0]["title"], "Backend Developer Intern")
        self.assertEqual(experience[0]["company"], "Synchores Information")

        education = sections["education_parsed"]
        self.assertTrue(any("University of the Philippines" in e["school"] for e in education))
        self.assertTrue(any("B.S. Computer Science" in e["degree"] for e in education))

        contact = sections["contact_parsed"]
        self.assertEqual(contact["github"], "github.com/juandelacruz")
        self.assertEqual(contact["email"], "juan.delacruz@email.com")


if __name__ == "__main__":
    unittest.main()
