import unittest

from app.analyzer.ats_checker import ATSCompatibilityChecker


SECTIONS = {
    "contact_parsed": {"email": "a@b.c", "phone": "1", "name": "N"},
    "_section_order": ["experience", "education", "skills"],
    "experience_parsed": [{"title": "Dev", "company": "Acme", "dates": "2024"}],
}


def pronoun_issues(text):
    result = ATSCompatibilityChecker().check(text, SECTIONS, {})
    return [issue for issue in result["issues"] if issue["issue"].startswith("Personal pronouns")]


def run(metadata=None, sections=None, filename=""):
    return ATSCompatibilityChecker().check(
        "Built services.", sections or SECTIONS, metadata or {}, filename=filename
    )


def issue_names(result):
    return [issue["issue"] for issue in result["issues"]]


class PronounWarningTests(unittest.TestCase):
    def test_pdf_pipe_contact_lines_are_ignored(self):
        # Anonymized fixture: contact-like lines are never scanned for pronouns.
        text = (
            "alex.doe@example.com I +1 555-010-0199 I Springfield\n"
            "https://example.com/portfolio I https://github.com/example\n"
            "486-Hour Internship I Shelbyville"
        )
        self.assertEqual(pronoun_issues(text), [])

    def test_regular_resume_text_has_no_false_positive_pronouns(self):
        self.assertEqual(pronoun_issues("Built backend schemas with MySQL and PostgreSQL\nWhack-a-Mole Arduino game"), [])

    def test_real_pronouns_are_counted(self):
        issues = pronoun_issues("I built the API.\nI led the team.\nMy work improved delivery.")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["issue"], "Personal pronouns detected (3x)")
        self.assertEqual(len(issues[0]["examples"]), 3)

    def test_two_pronouns_do_not_warn(self):
        self.assertEqual(pronoun_issues("I built the API.\nMy work improved delivery."), [])


class LayoutWarningTests(unittest.TestCase):
    """B9: PDF layout checks that used to be absent or DOCX-only."""

    def test_images_are_flagged(self):
        result = run({"image_count": 2})
        self.assertIn("Images/icons detected (2)", issue_names(result))
        self.assertNotIn("No images/icons detected", result["passed"])

    def test_single_image_is_flagged(self):
        result = run({"has_images": True})
        self.assertIn("Images/icons detected (1)", issue_names(result))

    def test_multi_column_layout_is_critical(self):
        result = run({"has_multi_column": True})
        issue = next(i for i in result["issues"] if i["issue"] == "Multi-column layout detected")
        self.assertEqual(issue["category"], "critical")

    def test_icon_font_is_flagged(self):
        result = run({"has_icon_font": True, "font_count": 1})
        self.assertIn("Icon font detected", issue_names(result))

    def test_too_many_fonts_are_flagged(self):
        result = run({"font_count": 3})
        self.assertIn("Multiple fonts detected (3)", issue_names(result))

    def test_one_or_two_fonts_are_fine(self):
        for count in (1, 2):
            result = run({"font_count": count})
            self.assertIn("Standard font usage", result["passed"])
            self.assertNotIn(f"Multiple fonts detected ({count})", issue_names(result))

    def test_header_or_footer_content_is_critical(self):
        for metadata in ({"has_headers": True}, {"has_footers": True}):
            result = run(metadata)
            issue = next(i for i in result["issues"] if i["issue"] == "Content in header/footer")
            self.assertEqual(issue["category"], "critical")

    def test_clean_layout_passes(self):
        result = run()
        self.assertEqual(result["issues"], [])
        self.assertEqual(result["score"], 100)
        for label in ("No images/icons detected", "Single-column layout", "Standard font usage", "Experience dates present"):
            self.assertIn(label, result["passed"])


class ExperienceDateTests(unittest.TestCase):
    """B9: dates are how ATS and recruiters judge tenure."""

    def test_missing_dates_are_flagged(self):
        sections = {**SECTIONS, "experience_parsed": [{"title": "Dev"}]}
        result = run(sections=sections)
        self.assertIn("1 experience entry missing dates", issue_names(result))

    def test_plural_entries(self):
        sections = {
            **SECTIONS,
            "experience_parsed": [{"title": "Dev"}, {"title": "Intern"}, {"title": "Lead", "dates": "2024"}],
        }
        result = run(sections=sections)
        self.assertIn("2 experience entries missing dates", issue_names(result))

    def test_no_experience_entries_is_not_flagged(self):
        sections = {**SECTIONS, "experience_parsed": []}
        result = run(sections=sections)
        self.assertFalse(any("missing dates" in name for name in issue_names(result)))


class FilenameTests(unittest.TestCase):
    """B9: file naming is only checked when a filename is supplied."""

    def test_safe_filename_passes(self):
        result = run(filename="alex-doe_resume.pdf")
        self.assertIn("ATS-friendly file name", result["passed"])

    def test_spaces_and_specials_are_flagged(self):
        for filename in ("Jane Doe Resume.pdf", "resume (1).pdf", "résumé.pdf"):
            result = run(filename=filename)
            self.assertIn("File name uses spaces or special characters", issue_names(result))

    def test_no_filename_skips_the_check(self):
        result = run(filename="")
        self.assertNotIn("ATS-friendly file name", result["passed"])
        self.assertFalse(any("File name" in name for name in issue_names(result)))


class LegacyMetadataTests(unittest.TestCase):
    """Old stored analyses have no B9 metadata keys; they must not break."""

    def test_missing_metadata_keys_default_to_clean(self):
        result = run({"has_tables": False, "page_count": 1})
        self.assertEqual(result["issues"], [])
        self.assertIn("Single-column layout", result["passed"])


if __name__ == "__main__":
    unittest.main()
