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
        self.assertEqual(self.parser._clean_degree("Senior High — ABM Strand"), "ABM Strand")
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
        self.assertEqual(experience[0]["company"], "Infotech Solutions")

        education = sections["education_parsed"]
        self.assertTrue(any("University of the Philippines" in e["school"] for e in education))
        self.assertTrue(any("B.S. Computer Science" in e["degree"] for e in education))

        contact = sections["contact_parsed"]
        self.assertEqual(contact["github"], "github.com/juandelacruz")
        self.assertEqual(contact["email"], "juan.delacruz@email.com")


class RealResumePatternTests(unittest.TestCase):
    """A15 follow-up: patterns taken from a real two-column PDF resume."""

    def setUp(self):
        self.parser = SectionParser()

    def test_labeled_skill_lines_stay_in_skills(self):
        # "Languages: JavaScript" under a TECHNICAL SKILLS header is content,
        # not a LANGUAGES section header.
        sections = self.parser.parse(
            "TECHNICAL SKILLS\n"
            "Languages: JavaScript, TypeScript, PHP, C++\n"
            "Frontend: React.js, Next.js, HTML5\n"
            "Backend: Node.js, NestJS, PHP\n"
            "Databases: MySQL, PostgreSQL\n"
            "DevOps & Tools: Docker, Nginx, Git"
        )
        order = sections["_section_order"]
        self.assertIn("skills", order)
        self.assertNotIn("languages", order)
        skills = sections["skills_parsed"]
        self.assertIn("JavaScript", skills)
        self.assertIn("React.js", skills)
        self.assertIn("Docker", skills)
        self.assertFalse(any("Languages" in s or "Frontend" in s or "DevOps" in s for s in skills))

    def test_company_name_wrapping_is_merged(self):
        raw = (
            "2026 Backend Developer Intern at Infotech Solutions\n"
            "Internship Technology Group\n"
            "486-Hour Internship I Imus, Cavite\n"
            "- Built backend schemas and GraphQL APIs\n"
        )
        entries = self.parser._parse_experience(raw)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "Backend Developer Intern")
        self.assertEqual(entries[0]["company"], "Infotech Solutions Technology Group | 486-Hour | Imus, Cavite")

    def test_clean_company_keeps_hyphenated_compounds(self):
        self.assertEqual(self.parser._clean_company("486-Hour"), "486-Hour")
        self.assertEqual(self.parser._clean_company("Full-Stack Developer"), "Full-Stack Developer")
        self.assertEqual(self.parser._clean_company("E-Commerce System"), "E-Commerce System")
        self.assertEqual(self.parser._clean_company("Acme - Full-Stack Developer"), "Acme — Full-Stack Developer")

    def test_clean_company_restores_pipe_from_capital_i(self):
        self.assertEqual(
            self.parser._clean_company("486-Hour Internship I Imus, Cavite"),
            "486-Hour | Imus, Cavite",
        )

    def test_clean_degree_strips_merged_label_before_degree_token(self):
        self.assertEqual(
            self.parser._clean_degree("College Bachelor of Science in Information Technology - Cum Laude"),
            "Bachelor of Science in Information Technology - Cum Laude",
        )

    def test_clean_degree_dedupes_duplicated_senior_high(self):
        self.assertEqual(
            self.parser._clean_degree("Senior High Senior High School, ABM Strand — Graduated with Highest Honors"),
            "Senior High School, ABM Strand — Graduated with Highest Honors",
        )

    def test_clean_degree_still_protects_university_names(self):
        self.assertEqual(self.parser._clean_degree("University of the Philippines"), "University of the Philippines")
        self.assertEqual(self.parser._clean_degree("University of Santo Tomas"), "University of Santo Tomas")
        self.assertEqual(self.parser._clean_degree("School, ABM Strand"), "ABM Strand")

    def test_inline_caps_label_anywhere_is_a_header(self):
        sections = self.parser.parse("EXPERIENCE\nBuilt REST APIs\nSKILLS: Python, React")
        self.assertEqual(sections["_section_order"], ["experience", "skills"])
        self.assertEqual(sections["skills_parsed"], ["Python", "React"])


class AnonymizedFixtureTests(unittest.TestCase):
    """F4: six more anonymized layouts, each targeting a parsing hazard."""

    def setUp(self):
        self.parser = SectionParser()

    def _parse(self, name):
        return self.parser.parse(load_fixture(f"{name}.txt"))

    def test_caps_headers_alternate_names_and_em_dash_dates(self):
        sections = self._parse("resume_caps_headers")
        order = sections["_section_order"]
        for expected in ("summary", "experience", "skills", "education", "certifications"):
            self.assertIn(expected, order)
        experience = sections["experience_parsed"]
        self.assertEqual(len(experience), 2)
        self.assertEqual(experience[0]["title"], "Senior Web Developer")
        self.assertEqual(experience[0]["company"], "Globex Corporation")
        self.assertEqual(experience[0]["dates"], "Jan 2022 — Present")
        self.assertEqual(len(experience[0]["bullets"]), 2)
        education = sections["education_parsed"]
        self.assertEqual(education[0]["school"], "Polytechnic University of the Philippines")
        self.assertEqual(education[0]["degree"], "B.S. Information Technology")
        skills = sections["skills_parsed"]
        self.assertIn("Laravel", skills)
        self.assertFalse(any("TECHNICAL" in s for s in skills))

    def test_skills_first_layout_and_no_phantom_portfolio(self):
        sections = self._parse("resume_skills_first")
        # skills detected even though it appears before summary/experience
        self.assertEqual(sections["_section_order"][:3], ["contact", "skills", "summary"])
        skills = sections["skills_parsed"]
        self.assertIn("Python", skills)
        self.assertIn("Docker", skills)
        self.assertIn("AWS", skills)
        # F4 regression: the email once spawned a fake "carlos.me" portfolio
        self.assertEqual(sections["contact_parsed"]["portfolio"], "")
        experience = sections["experience_parsed"]
        self.assertEqual(len(experience), 2)
        self.assertEqual(experience[0]["company"], "Delta Analytics")

    def test_experience_without_dates_still_parses(self):
        sections = self._parse("resume_no_dates")
        experience = sections["experience_parsed"]
        self.assertEqual(len(experience), 2)
        self.assertEqual(experience[0]["title"], "Junior Web Developer")
        self.assertEqual(experience[0]["company"], "Zeta Webworks")
        self.assertEqual(experience[0]["dates"], "")
        self.assertEqual(len(experience[0]["bullets"]), 2)
        self.assertEqual(experience[1]["dates"], "")
        education = sections["education_parsed"]
        self.assertEqual(education[0]["school"], "Pamantasan ng Lungsod ng Maynila")

    def test_two_column_artifacts_keep_education_fields_straight(self):
        sections = self._parse("resume_two_column")
        education = sections["education_parsed"]
        # F4 regression: the glued "College" label used to swap school/degree
        self.assertEqual(education[0]["school"], "University of the Philippines")
        self.assertEqual(education[0]["degree"], "Bachelor of Science in Information Technology")
        self.assertEqual(education[0]["dates"], "2020 - 2024")
        self.assertEqual(education[1]["school"], "Quezon City Science High School")
        # labeled skill lines under SKILLS stay skills (no LANGUAGES section)
        self.assertNotIn("languages", sections["_section_order"])
        skills = sections["skills_parsed"]
        self.assertIn("PHP", skills)
        self.assertIn("Laravel", skills)
        experience = sections["experience_parsed"]
        self.assertEqual(len(experience), 2)
        self.assertEqual(experience[0]["title"], "Senior Web Developer")

    def test_student_projects_get_dates_and_involvement_is_skipped(self):
        sections = self._parse("resume_student_projects")
        self.assertNotIn("experience", sections["_section_order"])
        projects = sections["projects_parsed"]
        # F4 regression: date lines used to split each project in two, and
        # involvement content used to leak in as fake entries
        self.assertEqual(len(projects), 2)
        self.assertEqual(projects[0]["title"], "Library Management System")
        self.assertEqual(projects[0]["dates"], "Feb 2024 - May 2024")
        self.assertEqual(len(projects[0]["bullets"]), 2)
        self.assertEqual(projects[1]["title"], "Campus Event Finder")
        self.assertEqual(projects[1]["dates"], "Sep 2023 - Dec 2023")
        self.assertFalse(any("LEADERSHIP" in (e.get("title") or "") for e in projects))
        education = sections["education_parsed"]
        self.assertEqual(len(education), 1)
        self.assertEqual(education[0]["school"], "University of Santo Tomas")
        # F4 regression: "Expected 2026" used to become a bogus second entry
        self.assertEqual(education[0]["dates"], "Expected 2026")

    def test_career_changer_to_separator_and_extra_sections(self):
        sections = self._parse("resume_career_changer")
        experience = sections["experience_parsed"]
        self.assertEqual(len(experience), 2)
        self.assertEqual(experience[0]["title"], "Data Analyst")
        self.assertEqual(experience[0]["dates"], "2015 to 2020")
        self.assertIn("certifications", sections["_section_order"])
        self.assertIn("languages", sections["_section_order"])
        self.assertIn("Excel", sections["skills_parsed"])
        self.assertIn("Power BI", sections["skills_parsed"])


if __name__ == "__main__":
    unittest.main()
