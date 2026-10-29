"""F12: structure tests for the split section parser.

Each parser class is exercised on its own, the splitter's section-boundary
rules are covered directly, and a size guard keeps the package from collapsing
back into one large module.
"""
import unittest
from pathlib import Path

from app.parser.section_parser import SectionParser
from app.parser.sections import (
    ContactParser,
    EducationParser,
    ExperienceParser,
    ProjectsParser,
    SectionSplitter,
    SkillsParser,
)

PARSER_DIR = Path(__file__).resolve().parents[1] / "app" / "parser"


class SectionSplitterTests(unittest.TestCase):
    def setUp(self):
        self.splitter = SectionSplitter()

    def test_named_sections_and_order(self):
        sections, order = self.splitter.split(
            "JANE DOE\n"
            "jane@example.com\n"
            "\n"
            "SUMMARY\n"
            "Backend developer.\n"
            "\n"
            "EXPERIENCE\n"
            "Acme Corp\n"
            "- Built REST APIs"
        )
        self.assertEqual(order, ["contact", "summary", "experience"])
        self.assertEqual(sections["summary"]["raw"], "Backend developer.")
        self.assertEqual(sections["experience"]["raw"], "Acme Corp\n- Built REST APIs")
        self.assertIn("JANE DOE", sections["contact"]["raw"])

    def test_blank_lines_inside_a_section_are_kept(self):
        sections, _ = self.splitter.split("SUMMARY\nFirst paragraph.\n\nSecond paragraph.")
        self.assertEqual(sections["summary"]["raw"], "First paragraph.\n\nSecond paragraph.")

    def test_inline_all_caps_header_feeds_remainder_to_body(self):
        sections, order = self.splitter.split("EXPERIENCE\nBuilt APIs\nSKILLS: Python, React")
        self.assertEqual(order, ["experience", "skills"])
        self.assertEqual(sections["skills"]["raw"], "Python, React")

    def test_mixed_case_label_inside_a_section_is_not_a_header(self):
        # "Languages: JavaScript" under SKILLS is content, not a LANGUAGES header.
        sections, order = self.splitter.split("SKILLS\nLanguages: JavaScript, TypeScript")
        self.assertEqual(order, ["skills"])
        self.assertEqual(sections["skills"]["raw"], "Languages: JavaScript, TypeScript")

    def test_references_section_is_dropped(self):
        sections, order = self.splitter.split(
            "EXPERIENCE\nAcme Corp\nREFERENCES\nAvailable upon request"
        )
        self.assertNotIn("references", order)
        self.assertEqual(sections["experience"]["raw"], "Acme Corp")

    def test_involvement_header_and_its_content_are_dropped(self):
        sections, order = self.splitter.split(
            "PROJECTS\nLibrary App\nLEADERSHIP\nPresident of the student council"
        )
        self.assertEqual(order, ["projects"])
        self.assertEqual(sections["projects"]["raw"], "Library App")

    def test_lines_before_the_first_header_become_contact(self):
        sections, order = self.splitter.split("JANE DOE\njane@example.com")
        self.assertEqual(order, ["contact"])
        self.assertEqual(sections["contact"]["raw"], "JANE DOE\njane@example.com")

    def test_detect_sec_ignores_long_sentences(self):
        self.assertIsNone(self.splitter._detect_sec("Built REST APIs with Python and React"))
        self.assertEqual(self.splitter._detect_sec("TECHNICAL SKILLS"), "skills")


class ContactParserTests(unittest.TestCase):
    def setUp(self):
        self.parser = ContactParser()

    def test_fields_are_parsed_independently(self):
        contact = self.parser.parse(
            "JANE DOE\n"
            "FULL STACK DEVELOPER\n"
            "jane@example.com | +63 917 123 4567\n"
            "LinkedIn: jane-doe\n"
            "GitHub: janedoe\n"
            "https://janedoe.dev"
        )
        self.assertEqual(contact["name"], "JANE DOE")
        self.assertEqual(contact["title"], "FULL STACK DEVELOPER")
        self.assertEqual(contact["email"], "jane@example.com")
        self.assertEqual(contact["phone"], "+63 917 123 4567")
        self.assertEqual(contact["linkedin"], "linkedin.com/in/jane-doe")
        self.assertEqual(contact["github"], "github.com/janedoe")
        self.assertEqual(contact["portfolio"], "https://janedoe.dev")

    def test_bare_handle_is_normalized(self):
        self.assertEqual(
            self.parser._normalize_handle("linkedin", "jane-doe"),
            "linkedin.com/in/jane-doe",
        )
        self.assertEqual(
            self.parser._normalize_handle("github", "janedoe"),
            "github.com/janedoe",
        )

    def test_empty_block_returns_empty_fields(self):
        contact = self.parser.parse("")
        self.assertEqual(contact["name"], "")
        self.assertEqual(contact["title"], "")
        self.assertEqual(contact["email"], "")


class ExperienceParserTests(unittest.TestCase):
    def setUp(self):
        self.parser = ExperienceParser()

    def test_role_company_dates_and_bullets(self):
        entries = self.parser.parse(
            "2026 Backend Developer Intern at Infotech Solutions\n"
            "Internship Technology Group\n"
            "486-Hour Internship I Imus, Cavite\n"
            "- Built backend schemas\n"
            "- Wrote GraphQL APIs"
        )
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "Backend Developer Intern")
        self.assertEqual(
            entries[0]["company"],
            "Infotech Solutions Technology Group | 486-Hour | Imus, Cavite",
        )
        self.assertEqual(len(entries[0]["bullets"]), 2)

    def test_bare_date_line_attaches_to_the_pending_title(self):
        entries = self.parser.parse("Software Engineer\nAcme Corp\nJan 2022 - Present\n- Built APIs")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["dates"], "Jan 2022 - Present")

    def test_references_stop_parsing(self):
        entries = self.parser.parse("Acme Corp\n- Built APIs\nREFERENCES\nOther person")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["bullets"], ["Built APIs"])

    def test_empty_text_returns_no_entries(self):
        self.assertEqual(self.parser.parse(""), [])
        self.assertEqual(self.parser.parse("   \n"), [])


class ProjectsParserTests(unittest.TestCase):
    def setUp(self):
        self.parser = ProjectsParser()

    def test_titles_dates_and_bullets(self):
        entries = self.parser.parse(
            "Library Management System\n"
            "Feb 2024 - May 2024\n"
            "- Built CRUD screens\n"
            "Campus Event Finder\n"
            "Sep 2023 - Dec 2023\n"
            "- Added search"
        )
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["title"], "Library Management System")
        self.assertEqual(entries[0]["dates"], "Feb 2024 - May 2024")
        self.assertEqual(entries[0]["bullets"], ["Built CRUD screens"])
        self.assertEqual(entries[1]["title"], "Campus Event Finder")

    def test_continuation_line_extends_the_last_bullet(self):
        entries = self.parser.parse("Library App\n- Built a small tool\nwith a local database")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["bullets"], ["Built a small tool with a local database"])

    def test_empty_text_returns_no_entries(self):
        self.assertEqual(self.parser.parse(""), [])


class EducationParserTests(unittest.TestCase):
    def setUp(self):
        self.parser = EducationParser()

    def test_degree_first_layout(self):
        entries = self.parser.parse(
            "B.S. Computer Science\nUniversity of the Philippines\n2020 - 2024"
        )
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["degree"], "B.S. Computer Science")
        self.assertEqual(entries[0]["school"], "University of the Philippines")
        self.assertEqual(entries[0]["dates"], "2020 - 2024")

    def test_expected_graduation_is_a_date_not_a_new_entry(self):
        entries = self.parser.parse(
            "University of Santo Tomas\nB.S. Computer Science\nExpected 2026"
        )
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["dates"], "Expected 2026")

    def test_a_second_school_starts_a_new_entry(self):
        entries = self.parser.parse(
            "University of the Philippines\nB.S. Computer Science, 2024\n"
            "University of Santo Tomas\nM.S. Data Science, 2026"
        )
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["school"], "University of the Philippines")
        self.assertEqual(entries[1]["school"], "University of Santo Tomas")

    def test_empty_text_returns_no_entries(self):
        self.assertEqual(self.parser.parse(""), [])


class SkillsParserTests(unittest.TestCase):
    def setUp(self):
        self.parser = SkillsParser()

    def test_category_labels_are_stripped_and_duplicates_removed(self):
        skills = self.parser.parse(
            "Languages: Python, JavaScript\n"
            "Frontend: React, React, Next.js"
        )
        self.assertEqual(skills, ["Python", "JavaScript", "React", "Next.js"])

    def test_bullet_glyphs_separate_skills(self):
        self.assertEqual(self.parser.parse("• Docker • AWS"), ["Docker", "AWS"])

    def test_empty_text_returns_no_skills(self):
        self.assertEqual(self.parser.parse(""), [])


class SectionParserCompositionTests(unittest.TestCase):
    """The public class wires the focused parsers together."""

    def setUp(self):
        self.parser = SectionParser()

    def test_parse_exposes_every_parsed_block(self):
        sections = self.parser.parse(
            "JANE DOE\njane@example.com\n"
            "\nSUMMARY\nBackend developer.\n"
            "\nEXPERIENCE\nSoftware Engineer at Acme Corp\n- Built APIs\n"
            "\nPROJECTS\nLibrary App\n- Built a tool\n"
            "\nEDUCATION\nB.S. Computer Science\nUniversity of the Philippines\n2020 - 2024\n"
            "\nSKILLS\nPython, React"
        )
        for key in (
            "contact_parsed",
            "experience_parsed",
            "projects_parsed",
            "education_parsed",
            "skills_parsed",
        ):
            self.assertIn(key, sections)
        self.assertEqual(sections["contact_parsed"]["name"], "JANE DOE")
        self.assertEqual(sections["experience_parsed"][0]["company"], "Acme Corp")
        self.assertEqual(sections["projects_parsed"][0]["title"], "Library App")
        self.assertEqual(sections["education_parsed"][0]["school"], "University of the Philippines")
        self.assertEqual(sections["skills_parsed"], ["Python", "React"])

    def test_compatibility_delegates_match_direct_parsers(self):
        text = "Acme Corp\n- Built APIs"
        self.assertEqual(self.parser._parse_experience(text), ExperienceParser().parse(text))
        self.assertEqual(self.parser._parse_projects(text), ProjectsParser().parse(text))
        self.assertEqual(self.parser._parse_skills("Python, React"), SkillsParser().parse("Python, React"))
        contact = "JANE DOE\njane@example.com"
        self.assertEqual(self.parser._parse_contact(contact), ContactParser().parse(contact))
        education = "B.S. Computer Science\nUniversity of the Philippines"
        self.assertEqual(self.parser._parse_education(education), EducationParser().parse(education))

    def test_shared_cleaning_helpers_are_still_reachable(self):
        self.assertEqual(self.parser._clean_company("486-Hour"), "486-Hour")
        self.assertEqual(self.parser._clean_degree("College"), "")


class ParserModuleSizeTests(unittest.TestCase):
    """F12 guard: keep the parser split into focused modules."""

    def _line_count(self, path: Path) -> int:
        return len(path.read_text(encoding="utf-8").splitlines())

    def test_section_modules_stay_focused(self):
        for path in sorted((PARSER_DIR / "sections").glob("*.py")):
            with self.subTest(module=path.name):
                self.assertLessEqual(
                    self._line_count(path),
                    400,
                    f"{path.name} grew past 400 lines — split it further",
                )

    def test_orchestrator_stays_small(self):
        self.assertLessEqual(
            self._line_count(PARSER_DIR / "section_parser.py"),
            150,
            "section_parser.py should orchestrate, not implement section parsing",
        )


if __name__ == "__main__":
    unittest.main()
