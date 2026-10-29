"""PDF resume export built on ReportLab.

The PDF mirrors the DOCX exporter's content (same sections, same accepted
rewrites, same confirmed skills) but uses a single-column layout with real
text, standard fonts, and no images so the result stays ATS-readable.
"""

import io
import os
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.export.content import ResumeContentBuilder, normalize_glyphs


# Two font files at most: the ATS checker warns when a PDF embeds more than
# two fonts. Bold is a separate face; subtitles use the muted color instead of
# italics so a resume we generate never trips our own warning.
_FONT_CANDIDATES: tuple[tuple[str, str], ...] = (
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
     "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf",
     "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
)

# Helvetica cannot draw these; transliterate only when no Unicode TTF is
# available. With Arial/DejaVu the symbols are embedded correctly.
_CURRENCY_FALLBACK = {
    "₱": "P",
    "₹": "Rs",
    "₩": "KRW",
    "₽": "RUB",
    "₪": "ILS",
    "₫": "VND",
    "₴": "UAH",
    "₦": "NGN",
}


def _register_fonts() -> tuple[str, str, bool]:
    """Return ``(regular, bold, supports_unicode)`` for this process."""
    registered = set(pdfmetrics.getRegisteredFontNames())
    if "ResumeSans" in registered and "ResumeSans-Bold" in registered:
        return "ResumeSans", "ResumeSans-Bold", True

    for regular_path, bold_path in _FONT_CANDIDATES:
        if not (os.path.exists(regular_path) and os.path.exists(bold_path)):
            continue
        try:
            pdfmetrics.registerFont(TTFont("ResumeSans", regular_path))
            pdfmetrics.registerFont(TTFont("ResumeSans-Bold", bold_path))
            pdfmetrics.registerFontFamily(
                "ResumeSans",
                normal="ResumeSans",
                bold="ResumeSans-Bold",
                italic="ResumeSans",
                boldItalic="ResumeSans-Bold",
            )
        except Exception:
            continue
        return "ResumeSans", "ResumeSans-Bold", True

    return "Helvetica", "Helvetica-Bold", False


class PdfExporter(ResumeContentBuilder):
    """Renders a tailored resume as a text-based, single-column PDF."""

    COLOR_PRIMARY_HEX = "#003366"
    COLOR_PRIMARY = colors.HexColor(COLOR_PRIMARY_HEX)
    COLOR_BODY = colors.HexColor("#1E1E1E")
    COLOR_MUTED = colors.HexColor("#505050")

    def __init__(self):
        self.font_regular, self.font_bold, self.unicode_fonts = _register_fonts()
        self.content_width = letter[0] - 0.9 * inch
        self._build_styles()

    def _build_styles(self):
        self.name_style = ParagraphStyle(
            "ResumeName",
            fontName=self.font_bold,
            fontSize=14,
            leading=16,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#0A0A0A"),
            spaceAfter=1,
        )
        self.title_style = ParagraphStyle(
            "ResumeTitle",
            fontName=self.font_bold,
            fontSize=10,
            leading=12,
            alignment=TA_CENTER,
            textColor=self.COLOR_PRIMARY,
            spaceAfter=3,
        )
        self.contact_style = ParagraphStyle(
            "ResumeContact",
            fontName=self.font_regular,
            fontSize=8.5,
            leading=11,
            alignment=TA_CENTER,
            textColor=self.COLOR_BODY,
            spaceAfter=6,
        )
        self.heading_style = ParagraphStyle(
            "ResumeHeading",
            fontName=self.font_bold,
            fontSize=10,
            leading=12,
            textColor=self.COLOR_PRIMARY,
            spaceBefore=5,
            spaceAfter=2,
        )
        self.body_style = ParagraphStyle(
            "ResumeBody",
            fontName=self.font_regular,
            fontSize=9.5,
            leading=11.5,
            textColor=self.COLOR_BODY,
            spaceAfter=2,
        )
        self.entry_style = ParagraphStyle(
            "ResumeEntry",
            parent=self.body_style,
            fontName=self.font_bold,
            spaceAfter=0,
        )
        self.muted_style = ParagraphStyle(
            "ResumeMuted",
            fontName=self.font_regular,
            fontSize=9,
            leading=11,
            textColor=self.COLOR_MUTED,
            spaceAfter=1,
        )
        self.date_style = ParagraphStyle(
            "ResumeDate",
            parent=self.muted_style,
            alignment=TA_RIGHT,
            spaceAfter=0,
        )
        self.detail_style = ParagraphStyle(
            "ResumeDetail",
            fontName=self.font_regular,
            fontSize=9,
            leading=11,
            textColor=self.COLOR_BODY,
            spaceAfter=0,
        )
        self.bullet_style = ParagraphStyle(
            "ResumeBullet",
            fontName=self.font_regular,
            fontSize=9.5,
            leading=11.5,
            textColor=self.COLOR_BODY,
            leftIndent=12,
            bulletIndent=2,
            spaceAfter=1.5,
            bulletFontName=self.font_regular,
            bulletFontSize=9.5,
        )

    # ---------------------------------------------------------------- #
    # public entry point
    # ---------------------------------------------------------------- #

    def export_tailored(
        self,
        sections: dict,
        missing_keywords: list[str] | None = None,
        rewritten_bullets: dict | None = None,
        target_role: str = "",
        match_title: bool = False,
    ) -> bytes:
        story = []
        contact = sections.get("contact_parsed", {}) or {}
        self._add_header(
            story, contact, target_role, self.resume_title(sections), match_title
        )

        if sections.get("summary", {}).get("raw"):
            self._heading(story, "SUMMARY")
            # A4: no silent edits to the candidate's own words.
            story.append(
                Paragraph(
                    self._safe(self.summary_text(sections["summary"]["raw"])),
                    self.body_style,
                )
            )

        edu_parsed = sections.get("education_parsed")
        edu_raw = sections.get("education", {}).get("raw", "")
        if edu_parsed or edu_raw:
            self._heading(story, "EDUCATION")
            if edu_parsed:
                for entry in edu_parsed:
                    self._add_education_entry(story, entry)
            else:
                self._add_entries(story, edu_raw)

        if sections.get("skills", {}).get("raw"):
            self._heading(story, "TECHNICAL SKILLS")
            self._add_skills(
                story, sections["skills"]["raw"], missing_keywords
            )

        exp_parsed = sections.get("experience_parsed")
        exp_raw = sections.get("experience", {}).get("raw", "")
        if exp_parsed or exp_raw:
            self._heading(story, "EXPERIENCE")
            if exp_parsed:
                for entry in exp_parsed:
                    self._add_structured_entry(story, entry, rewritten_bullets)
            else:
                self._add_entries(
                    story, self._apply_rewrites(exp_raw, rewritten_bullets)
                )

        proj_parsed = sections.get("projects_parsed")
        proj_raw = sections.get("projects", {}).get("raw", "")
        if proj_parsed or proj_raw:
            self._heading(story, "PROJECTS")
            if proj_parsed:
                for entry in proj_parsed:
                    self._add_structured_entry(story, entry, rewritten_bullets)
            else:
                self._add_entries(
                    story, self._apply_rewrites(proj_raw, rewritten_bullets)
                )

        cert_raw = sections.get("certifications", {}).get("raw", "")
        if cert_raw:
            self._add_list_section(story, "CERTIFICATIONS", cert_raw)

        lang_raw = sections.get("languages", {}).get("raw", "")
        if lang_raw:
            self._add_list_section(story, "LANGUAGES", lang_raw)

        name = (contact.get("name") or "").strip()
        buffer = io.BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=0.45 * inch,
            rightMargin=0.45 * inch,
            topMargin=0.4 * inch,
            bottomMargin=0.4 * inch,
            title=name or "Resume",
            author=name,
            subject="Resume",
            creator="LandIt",
        )
        document.build(story)
        return buffer.getvalue()

    # ---------------------------------------------------------------- #
    # header / contact
    # ---------------------------------------------------------------- #

    def _add_header(
        self,
        story: list,
        contact: dict,
        target_role: str,
        resume_title: str,
        match_title: bool,
    ):
        name = (contact.get("name") or "").strip()
        if name:
            story.append(Paragraph(self._safe(name.upper()), self.name_style))

        # A4: the resume's own title wins unless the user explicitly opts in.
        job_title = (target_role or "").strip()
        if job_title.lower() == "string":  # legacy placeholder value
            job_title = ""
        chosen = (
            job_title if (match_title and job_title) else (resume_title or "").strip()
        )
        if chosen:
            story.append(Paragraph(self._safe(chosen.upper()), self.title_style))

        parts = self.contact_parts(contact)
        if parts:
            rendered = []
            for url, text in parts:
                label = self._safe(text)
                if url:
                    rendered.append(
                        f'<link href="{self._safe_attr(url)}">{label}</link>'
                    )
                else:
                    rendered.append(label)
            story.append(
                Paragraph("   |   ".join(rendered), self.contact_style)
            )

    # ---------------------------------------------------------------- #
    # sections
    # ---------------------------------------------------------------- #

    def _heading(self, story: list, title: str):
        story.append(Paragraph(self._safe(title.upper()), self.heading_style))
        story.append(
            HRFlowable(
                width="100%",
                thickness=0.6,
                color=self.COLOR_PRIMARY,
                spaceBefore=0,
                spaceAfter=3,
            )
        )

    def _add_education_entry(self, story: list, entry: dict):
        parts = self.education_parts(entry)
        primary = parts["primary"]
        if not primary:
            return
        self._add_entry_header(
            story, primary, parts["dates"]
        )
        if parts["secondary"]:
            story.append(
                Paragraph(self._safe(parts["secondary"]), self.muted_style)
            )
        for detail in parts["details"]:
            story.append(Paragraph(self._safe(detail), self.detail_style))
        story.append(Spacer(1, 2))

    def _add_structured_entry(
        self, story: list, entry: dict, rewritten: dict | None
    ):
        parts = self.entry_parts(entry)
        title = parts["title"]
        bullets = entry.get("bullets") or []
        if not title and not bullets:
            return

        self._add_entry_header(story, title, parts["dates"])
        if parts["subtitle"]:
            story.append(Paragraph(self._safe(parts["subtitle"]), self.muted_style))

        for text in self.entry_bullets(bullets, rewritten):
            story.append(
                Paragraph(
                    self._safe(text), self.bullet_style, bulletText="•"
                )
            )
        story.append(Spacer(1, 3))

    def _add_entry_header(self, story: list, title: str, dates: str):
        title_paragraph = Paragraph(self._safe(title), self.entry_style)
        if not dates:
            story.append(title_paragraph)
            return
        table = Table(
            [[title_paragraph, Paragraph(self._safe(dates), self.date_style)]],
            colWidths=[self.content_width - 100, 100],
        )
        table.setStyle(
            TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ])
        )
        story.append(table)

    def _add_entries(self, story: list, text: str):
        for line in self._clean_lines(text):
            if self.BULLET_RE.match(line):
                content = self.BULLET_RE.sub("", line).strip()
                story.append(
                    Paragraph(
                        self._safe(content), self.bullet_style, bulletText="•"
                    )
                )
                continue
            style = self.entry_style if self.DATE_RE.match(line) else self.body_style
            story.append(Paragraph(self._safe(line), style))

    def _add_list_section(self, story: list, title: str, text: str):
        lines = self._clean_lines(text)
        if not lines:
            return
        self._heading(story, title)
        self._add_entries(story, "\n".join(lines))

    def _add_skills(
        self, story: list, text: str, missing_keywords: list[str] | None
    ):
        lines, leftover = self.skills_lines(text, missing_keywords)
        for line in lines:
            if ":" in line:
                label, _, rest = line.partition(":")
                story.append(
                    Paragraph(
                        f"<b>{self._safe(label.strip())}:</b> "
                        f"{self._safe(rest.strip())}",
                        self.body_style,
                    )
                )
            else:
                story.append(Paragraph(self._safe(line), self.body_style))
        if leftover:
            story.append(
                Paragraph(
                    f"<b>Additional Skills:</b> {self._safe(', '.join(leftover))}",
                    self.body_style,
                )
            )

    # ---------------------------------------------------------------- #
    # text safety
    # ---------------------------------------------------------------- #

    def _safe(self, text: str) -> str:
        cleaned = normalize_glyphs(text or "")
        if not self.unicode_fonts:
            for symbol, replacement in _CURRENCY_FALLBACK.items():
                cleaned = cleaned.replace(symbol, replacement)
        return escape(cleaned)

    @staticmethod
    def _safe_attr(text: str) -> str:
        return escape(text or "", {'"': "&quot;"})
