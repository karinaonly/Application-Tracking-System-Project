import io
import unittest

from docx import Document
from docx.oxml.ns import qn

from app.export.docx_exporter import DocxExporter


def document_text(data: bytes) -> str:
    """Return every paragraph's visible text, including hyperlink runs.

    python-docx's ``Paragraph.text`` skips text nested inside ``w:hyperlink``,
    so read the XML text nodes instead.
    """
    doc = Document(io.BytesIO(data))
    lines = []
    for paragraph in doc.paragraphs:
        lines.append("".join(node.text or "" for node in paragraph._p.iter(qn("w:t"))))
    return "\n".join(lines)


def make_sections() -> dict:
    return {
        "contact_parsed": {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "phone": "555-123-4567",
            "location": "Manila, PH",
            "portfolio": "janedoe.dev",
            "linkedin": "linkedin.com/in/janedoe",
            "github": "github.com/janedoe",
        },
        "summary": {"raw": "Backend developer."},
        "skills": {"raw": "Languages: Python, JavaScript, TypeScript, SQL"},
        "education_parsed": [],
        "experience_parsed": [
            {
                "title": "Backend Engineer",
                "company": "Acme",
                "dates": "2023 - 2025",
                "bullets": [
                    "Built APIs with JavaScript, TypeScript, PostgreSQL, MongoDB, and GitHub Actions",
                    "Used FastAPI and GraphQL with SQLAlchemy and SQLModel on AWS",
                    "Shipped iOS and Android clients with WebSockets and NoSQL stores",
                    "Practiced DevOps and improved a WordWord pipeline",
                ],
            }
        ],
        "projects_parsed": [],
        "certifications": {
            "raw": (
                "AWS Certified Cloud Practitioner - 2024\n"
                "Certified Kubernetes Administrator"
            )
        },
        "languages": {"raw": "English - Fluent\nFilipino - Native"},
    }


class DocxExporterCamelCaseTests(unittest.TestCase):
    def setUp(self):
        self.text = document_text(DocxExporter().export_tailored(make_sections()))

    def test_canonical_tech_names_are_not_split(self):
        for expected in (
            "JavaScript",
            "TypeScript",
            "PostgreSQL",
            "MongoDB",
            "GitHub",
            "GitHub Actions",
            "FastAPI",
            "GraphQL",
            "SQLAlchemy",
            "SQLModel",
            "iOS",
            "WebSockets",
            "NoSQL",
            "DevOps",
        ):
            with self.subTest(term=expected):
                self.assertIn(expected, self.text)

    def test_broken_camel_case_spellings_are_absent(self):
        for broken in (
            "Java Script",
            "Type Script",
            "Postgre SQL",
            "Mongo DB",
            "Git Hub",
            "Fast API",
            "Graph QL",
            "i OS",
            "Web Sockets",
            "No SQL",
            "Dev Ops",
        ):
            with self.subTest(broken=broken):
                self.assertNotIn(broken, self.text)

    def test_unknown_camel_case_still_splits(self):
        self.assertIn("Word Word", self.text)
        self.assertNotIn("WordWord", self.text)


class DocxExporterDroppedContentTests(unittest.TestCase):
    def test_linkedin_and_github_both_render_in_header(self):
        text = document_text(DocxExporter().export_tailored(make_sections()))

        self.assertIn("linkedin.com/in/janedoe", text)
        self.assertIn("github.com/janedoe", text)

    def test_certifications_and_languages_render(self):
        text = document_text(DocxExporter().export_tailored(make_sections()))

        self.assertIn("CERTIFICATIONS", text)
        self.assertIn("AWS Certified Cloud Practitioner - 2024", text)
        self.assertIn("Certified Kubernetes Administrator", text)
        self.assertIn("LANGUAGES", text)
        self.assertIn("English - Fluent", text)
        self.assertIn("Filipino - Native", text)

    def test_empty_sections_do_not_add_headings(self):
        sections = make_sections()
        sections.pop("certifications")
        sections.pop("languages")

        text = document_text(DocxExporter().export_tailored(sections))

        self.assertNotIn("CERTIFICATIONS", text)
        self.assertNotIn("LANGUAGES", text)


if __name__ == "__main__":
    unittest.main()
