import io
import unittest

import pdfplumber

from app.export.pdf_exporter import PdfExporter
from app.parser.text_extractor import TextExtractor


def pdf_text(data: bytes) -> str:
    """Extract the visible text from every page of a generated PDF."""
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def make_sections() -> dict:
    return {
        "contact_parsed": {
            "name": "Jane Doe",
            "title": "Backend Developer",
            "email": "jane@example.com",
            "phone": "555-123-4567",
            "location": "Manila, PH",
            "portfolio": "janedoe.dev",
            "linkedin": "linkedin.com/in/janedoe",
            "github": "github.com/janedoe",
        },
        "summary": {"raw": "Backend developer who ships reliable APIs."},
        "education_parsed": [{
            "school": "State University",
            "degree": "BS Computer Science",
            "dates": "2022 - 2026",
            "details": ["Dean's List"],
        }],
        "skills": {"raw": "Languages: Python, JavaScript\nDatabases: MySQL"},
        "experience_parsed": [{
            "title": "Backend Developer",
            "company": "Northwind Labs",
            "dates": "2024 - 2025",
            "bullets": [
                "Built APIs for the platform using Python",
                "Reduced latency by 40%",
            ],
        }],
        "projects_parsed": [{
            "title": "Inventory Service",
            "subtitle": "Personal project",
            "dates": "2025",
            "bullets": ["Automated stock reconciliation"],
        }],
        "certifications": {"raw": "AWS Cloud Practitioner"},
        "languages": {"raw": "English, Filipino"},
    }


class PdfExporterContentTests(unittest.TestCase):
    """D5: the PDF must say exactly what the DOCX says."""

    def setUp(self):
        self.exporter = PdfExporter()
        self.text = pdf_text(self.exporter.export_tailored(make_sections()))

    def test_output_is_a_pdf(self):
        self.assertTrue(
            self.exporter.export_tailored(make_sections()).startswith(b"%PDF")
        )

    def test_contact_and_every_section_render(self):
        self.assertIn("JANE DOE", self.text)
        self.assertIn("BACKEND DEVELOPER", self.text)
        self.assertIn("jane@example.com", self.text)
        self.assertIn("linkedin.com/in/janedoe", self.text)
        self.assertIn("SUMMARY", self.text)
        self.assertIn("EDUCATION", self.text)
        self.assertIn("State University", self.text)
        self.assertIn("BS Computer Science", self.text)
        self.assertIn("TECHNICAL SKILLS", self.text)
        self.assertIn("EXPERIENCE", self.text)
        self.assertIn("Northwind Labs", self.text)
        self.assertIn("Built APIs for the platform using Python", self.text)
        self.assertIn("PROJECTS", self.text)
        self.assertIn("Inventory Service", self.text)
        self.assertIn("CERTIFICATIONS", self.text)
        self.assertIn("AWS Cloud Practitioner", self.text)
        self.assertIn("LANGUAGES", self.text)
        self.assertIn("English, Filipino", self.text)

    def test_empty_sections_do_not_add_headings(self):
        text = pdf_text(
            self.exporter.export_tailored({
                "contact_parsed": {"name": "Jane Doe"},
            })
        )
        for heading in (
            "SUMMARY", "EDUCATION", "TECHNICAL SKILLS", "EXPERIENCE",
            "PROJECTS", "CERTIFICATIONS", "LANGUAGES",
        ):
            self.assertNotIn(heading, text)

    def test_resume_title_is_used_by_default(self):
        self.assertIn("BACKEND DEVELOPER", self.text)
        self.assertNotIn("DATA ANALYST", self.text)

    def test_job_title_is_only_used_when_requested(self):
        text = pdf_text(self.exporter.export_tailored(
            make_sections(), target_role="Data Analyst", match_title=True
        ))
        self.assertIn("DATA ANALYST", text)
        self.assertNotIn("BACKEND DEVELOPER", text)


class PdfExporterRewriteTests(unittest.TestCase):
    """C6/A5: only accepted, placeholder-free rewrites reach the PDF."""

    def setUp(self):
        self.exporter = PdfExporter()

    def _experience_only(self) -> dict:
        return {
            "contact_parsed": {"name": "Jane Doe"},
            "experience_parsed": [{
                "title": "Developer",
                "company": "Northwind Labs",
                "bullets": ["Did tasks for the team"],
            }],
        }

    def test_accepted_rewrite_replaces_the_bullet(self):
        text = pdf_text(self.exporter.export_tailored(
            self._experience_only(),
            rewritten_bullets={"Did tasks for the team": "Led a 5-member team"},
        ))
        self.assertIn("Led a 5-member team", text)
        self.assertNotIn("Did tasks for the team", text)

    def test_placeholder_rewrite_keeps_the_original(self):
        text = pdf_text(self.exporter.export_tailored(
            self._experience_only(),
            rewritten_bullets={"Did tasks for the team": "Led [X]-member team"},
        ))
        self.assertIn("Did tasks for the team", text)
        self.assertNotIn("[X]", text)

    def test_empty_rewrite_keeps_the_original(self):
        text = pdf_text(self.exporter.export_tailored(
            self._experience_only(),
            rewritten_bullets={"Did tasks for the team": ""},
        ))
        self.assertIn("Did tasks for the team", text)

    def test_legacy_ai_output_mapping_still_applies(self):
        text = pdf_text(self.exporter.export_tailored(
            self._experience_only(),
            rewritten_bullets={
                "Did tasks for the team": {"ai_output": "Led a 5-member team"}
            },
        ))
        self.assertIn("Led a 5-member team", text)


class PdfExporterKeywordTests(unittest.TestCase):
    """A3: only confirmed hard skills are folded into the Skills section."""

    def setUp(self):
        self.exporter = PdfExporter()

    def _skills_only(self) -> dict:
        return {
            "contact_parsed": {"name": "Jane Doe"},
            "skills": {"raw": "Languages: Python\nDatabases: MySQL"},
        }

    def test_confirmed_keywords_fold_into_matching_lines(self):
        text = pdf_text(self.exporter.export_tailored(
            self._skills_only(), missing_keywords=["SQL", "Docker"]
        ))
        self.assertIn("Databases: MySQL, SQL", text)
        self.assertIn("Additional Skills: Docker", text)

    def test_soft_skills_are_never_added(self):
        text = pdf_text(self.exporter.export_tailored(
            self._skills_only(),
            missing_keywords=["Communication", "Docker"],
        ))
        self.assertNotIn("Communication", text)
        self.assertIn("Docker", text)

    def test_keyword_already_present_is_not_duplicated(self):
        text = pdf_text(self.exporter.export_tailored(
            self._skills_only(), missing_keywords=["Python"]
        ))
        self.assertEqual(text.count("Python"), 1)


class PdfExporterGlyphTests(unittest.TestCase):
    """Currency symbols and dashes must survive the PDF conversion."""

    def test_currency_and_dashes_render(self):
        exporter = PdfExporter()
        text = pdf_text(exporter.export_tailored({
            "contact_parsed": {"name": "Jane Doe"},
            "summary": {
                "raw": "Saved ₱50,000 per month – cut costs — fast."
            },
        }))
        self.assertIn("50,000", text)
        self.assertIn("–", text)
        self.assertIn("—", text)
        if exporter.unicode_fonts:
            self.assertIn("₱", text)
        else:
            # Helvetica cannot draw the peso sign; the fallback transliterates.
            self.assertIn("P50,000", text)

    def test_nonbreaking_hyphens_are_normalized(self):
        text = pdf_text(PdfExporter().export_tailored({
            "contact_parsed": {"name": "Jane Doe"},
            "summary": {"raw": "Cross\u2011functional work"},
        }))
        self.assertIn("Cross-functional work", text)


class PdfExporterAtsMetadataTests(unittest.TestCase):
    """A resume we generate must not trip our own ATS warnings (B9)."""

    def test_generated_pdf_is_clean(self):
        data = PdfExporter().export_tailored(make_sections())
        result = TextExtractor().extract(data, ".pdf")
        metadata = result["metadata"]

        self.assertFalse(metadata["has_tables"])
        self.assertFalse(metadata["has_images"])
        self.assertFalse(metadata["has_icon_font"])
        self.assertFalse(metadata["has_multi_column"])
        self.assertFalse(metadata["has_headers"])
        self.assertFalse(metadata["has_footers"])
        self.assertLessEqual(metadata["font_count"], 2)
        self.assertIn("JANE DOE", result["raw_text"])


if __name__ == "__main__":
    unittest.main()
