import io
import re
from typing import Any

import docx
import docx.opc.constants
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls, qn

from app.common.skills import HARD_SKILLS


_CAMEL_BOUNDARY_RE = re.compile(r"[a-z][A-Z]")

# Glyphs that several DOCX viewers cannot render: PDF and AI output can
# smuggle in Unicode hyphen variants that show up as tofu boxes (□) in the
# exported resume. They all map to a plain ASCII hyphen. En/em dashes
# (U+2013/U+2014) are intentionally kept — Arial renders them and the parser
# uses " — " as its canonical separator.
_BAD_DASH_RE = re.compile(
    r"[\u2010\u2011\u2012\u2015\u2212\uFE58\uFE63\u00AD\uFFFD]"
)

def _normalize_glyphs(text: str) -> str:
    """Replace unrenderable dash glyphs with ASCII hyphens."""
    return _BAD_DASH_RE.sub("-", text)

# Brand/contact names that are not in the skills taxonomy but must keep their
# internal capital (A14 renders them; A13 must not split them).
_EXTRA_CANONICAL_TERMS = frozenset({
    "LinkedIn",
    "DevOps",
    "NestJS",
    "OpenAPI",
    "WordPress",
    "SharePoint",
})

# Only terms with an intentional lower-to-upper transition need protection.
# Longest first so "GitHub Actions" wins over "GitHub".
CANONICAL_TECH_TERMS = tuple(sorted(
    {name for name in HARD_SKILLS if _CAMEL_BOUNDARY_RE.search(name)}
    | set(_EXTRA_CANONICAL_TERMS),
    key=len,
    reverse=True,
))
TECH_TERM_RE = re.compile(
    r"(?<![A-Za-z])("
    + "|".join(re.escape(term) for term in CANONICAL_TECH_TERMS)
    + r")(?![A-Za-z])",
    re.I,
)


class DocxExporter:
    """
    Renders a tailored resume as a .docx using Arial typography.
    Prefers *_parsed structured sections when available.
    """

    DATE_RE = re.compile(r"^\d{4}(\s*[-–—]\s*\d{4})?\b")
    BULLET_RE = re.compile(r"^[•\-\*]\s*")
    PLACEHOLDER_RE = re.compile(r"\[[^\]]{1,30}\]")
    # Left-column labels that sometimes leak from the master resume
    LABEL_RE = re.compile(
        r"^(College|Senior\s*High(?:\s*School)?|University|Institute|"
        r"Internship|Capstone|Academic|Freelance|Part[- ]?Time|"
        r"Full[- ]?Time|Contract|Volunteer|Personal)$",
        re.I,
    )

    FONT_FAMILY = "Arial"
    COLOR_PRIMARY_HEX = "003366"
    COLOR_PRIMARY_RGB = RGBColor(0, 51, 102)
    COLOR_BODY_RGB = RGBColor(30, 30, 30)
    COLOR_MUTED_RGB = RGBColor(80, 80, 80)

    FLUFF = {
        "development", "engineering", "working", "experience",
        "application", "applications", "skills", "hands-on",
        "string", "ability", "role", "system", "systems", "team",
        "you", "your", "we", "our", "us", "they", "them", "who",
        "what", "help", "work", "looking", "about", "join",
        "testing", "deployment", "execution", "job", "responsibilities",
        "proprietary", "data", "requirements", "qualifications",
    }

    # ---------------------------------------------------------------- #
    # public entry point
    # ---------------------------------------------------------------- #

    def export_tailored(
        self,
        sections: dict,
        missing_keywords: list[str] | None = None,
        rewritten_bullets: dict | None = None,
        target_role: str = "",
    ) -> bytes:
        doc = docx.Document()
        self._setup_page(doc)
        self._setup_base_style(doc)
        self._setup_bullet_style(doc)

        c = sections.get("contact_parsed", {}) or {}
        self._add_header(doc, c, target_role)

        if sections.get("summary", {}).get("raw"):
            self._heading(doc, "SUMMARY")
            self._add_flow_text(
                doc, sections["summary"]["raw"].replace("Aspiring ", "")
            )

        # ✅ Prefer structured education_parsed
        edu_parsed = sections.get("education_parsed")
        edu_raw = sections.get("education", {}).get("raw", "")
        if edu_parsed or edu_raw:
            self._heading(doc, "EDUCATION")
            if edu_parsed:
                for entry in edu_parsed:
                    self._add_education_entry(doc, entry)
            else:
                self._add_entries(doc, edu_raw)

        if sections.get("skills", {}).get("raw"):
            self._heading(doc, "TECHNICAL SKILLS")
            self._add_skills(doc, sections["skills"]["raw"], missing_keywords)

        exp_parsed = sections.get("experience_parsed")
        exp_raw = sections.get("experience", {}).get("raw", "")
        if exp_parsed or exp_raw:
            self._heading(doc, "EXPERIENCE")
            if exp_parsed:
                for entry in exp_parsed:
                    self._add_structured_entry(doc, entry, rewritten_bullets)
            else:
                exp_text = self._apply_rewrites(exp_raw, rewritten_bullets)
                self._add_entries(doc, exp_text)

        proj_parsed = sections.get("projects_parsed")
        proj_raw = sections.get("projects", {}).get("raw", "")
        if proj_parsed or proj_raw:
            self._heading(doc, "PROJECTS")
            if proj_parsed:
                for entry in proj_parsed:
                    self._add_structured_entry(doc, entry, rewritten_bullets)
            else:
                proj_text = self._apply_rewrites(proj_raw, rewritten_bullets)
                self._add_entries(doc, proj_text, trailing_space=False)

        cert_raw = sections.get("certifications", {}).get("raw", "")
        if cert_raw:
            self._add_list_section(doc, "CERTIFICATIONS", cert_raw)

        lang_raw = sections.get("languages", {}).get("raw", "")
        if lang_raw:
            self._add_list_section(doc, "LANGUAGES", lang_raw)

        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        return buf.getvalue()

    # ---------------------------------------------------------------- #
    # setup
    # ---------------------------------------------------------------- #

    def _setup_page(self, doc):
        for s in doc.sections:
            s.top_margin = Inches(0.4)
            s.bottom_margin = Inches(0.4)
            s.left_margin = Inches(0.45)
            s.right_margin = Inches(0.45)
        self.page_width = Inches(7.6)

    def _setup_base_style(self, doc):
        style: Any = doc.styles["Normal"]
        style.font.name = self.FONT_FAMILY
        style.font.size = Pt(9.5)
        style.font.color.rgb = self.COLOR_BODY_RGB
        style.paragraph_format.space_after = Pt(0)
        style.paragraph_format.line_spacing = 1.08
        # Force Arial into the style's rFonts slot
        rPr = style.element.get_or_add_rPr()
        rFonts = rPr.get_or_add_rFonts()
        rFonts.set(qn("w:ascii"), self.FONT_FAMILY)
        rFonts.set(qn("w:hAnsi"), self.FONT_FAMILY)
        rFonts.set(qn("w:eastAsia"), self.FONT_FAMILY)
        rFonts.set(qn("w:cs"), self.FONT_FAMILY)

    def _setup_bullet_style(self, doc):
        existing = [s.name for s in doc.styles]
        if "ResumeBullet" in existing:
            return
        bullet_style = doc.styles.add_style("ResumeBullet", WD_STYLE_TYPE.PARAGRAPH)
        bullet_style.base_style = doc.styles["List Bullet"]
        bullet_style.font.name = self.FONT_FAMILY
        bullet_style.font.size = Pt(9.5)
        bullet_style.font.color.rgb = self.COLOR_BODY_RGB
        rPr = bullet_style.element.get_or_add_rPr()
        rFonts = rPr.get_or_add_rFonts()
        rFonts.set(qn("w:ascii"), self.FONT_FAMILY)
        rFonts.set(qn("w:hAnsi"), self.FONT_FAMILY)
        rFonts.set(qn("w:eastAsia"), self.FONT_FAMILY)
        rFonts.set(qn("w:cs"), self.FONT_FAMILY)
        pf = bullet_style.paragraph_format
        pf.space_after = Pt(1.5)
        pf.line_spacing = 1.05
        pf.left_indent = Inches(0.22)
        pf.first_line_indent = Inches(-0.15)

    def _force_font(self, run, size_pt=None, bold=None, italic=None, color=None):
        """Make Arial actually stick on this run."""
        run.font.name = self.FONT_FAMILY
        rPr = run._element.get_or_add_rPr()
        rFonts = rPr.get_or_add_rFonts()
        rFonts.set(qn("w:ascii"), self.FONT_FAMILY)
        rFonts.set(qn("w:hAnsi"), self.FONT_FAMILY)
        rFonts.set(qn("w:eastAsia"), self.FONT_FAMILY)
        rFonts.set(qn("w:cs"), self.FONT_FAMILY)
        if size_pt is not None:
            run.font.size = Pt(size_pt)
        if bold is not None:
            run.bold = bold
        if italic is not None:
            run.italic = italic
        if color is not None:
            run.font.color.rgb = color

    # ---------------------------------------------------------------- #
    # header / contact
    # ---------------------------------------------------------------- #

    def _add_header(self, doc, c: dict, target_role: str):
        if c.get("name"):
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(1)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(c["name"].upper())
            self._force_font(r, size_pt=14, bold=True, color=RGBColor(10, 10, 10))

        clean_role = (
            target_role.strip().upper()
            if target_role and target_role.strip().lower() not in ("string", "")
            else "FULL STACK DEVELOPER"
        )
        p_sub = doc.add_paragraph()
        p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_sub.paragraph_format.space_after = Pt(3)
        r_sub = p_sub.add_run(clean_role)
        self._force_font(r_sub, size_pt=10, bold=True, color=self.COLOR_PRIMARY_RGB)

        p_cnt = doc.add_paragraph()
        p_cnt.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cnt.paragraph_format.space_after = Pt(6)

        parts: list[tuple[str | None, str]] = []
        if c.get("email"):
            parts.append((f"mailto:{c['email']}", c["email"]))
        if c.get("phone"):
            parts.append((None, c["phone"]))
        if c.get("location"):
            parts.append((None, c["location"]))
        if c.get("portfolio"):
            url = c["portfolio"]
            full_url = url if url.startswith("http") else f"https://{url}"
            parts.append((full_url, url))
        if c.get("linkedin"):
            url = c["linkedin"]
            full_url = url if url.startswith("http") else f"https://{url}"
            parts.append((full_url, url))
        if c.get("github"):
            url = c["github"]
            full_url = url if url.startswith("http") else f"https://{url}"
            parts.append((full_url, url))

        for i, (url, text) in enumerate(parts):
            if i > 0:
                sep = p_cnt.add_run("   |   ")
                self._force_font(sep, size_pt=8.5, color=self.COLOR_MUTED_RGB)
            if url:
                self._add_hyperlink(p_cnt, url, text, size=8.5)
            else:
                run = p_cnt.add_run(text)
                self._force_font(run, size_pt=8.5, color=self.COLOR_BODY_RGB)

    def _add_hyperlink(self, paragraph, url: str, text: str, size: float = 8.5):
        part = paragraph.part
        r_id = part.relate_to(
            url, docx.opc.constants.RELATIONSHIP_TYPE.HYPERLINK, is_external=True
        )
        hyperlink_xml = (
            f'<w:hyperlink {nsdecls("w")} '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            f'r:id="{r_id}">'
            "<w:r><w:rPr>"
            f'<w:rFonts w:ascii="{self.FONT_FAMILY}" w:hAnsi="{self.FONT_FAMILY}" '
            f'w:eastAsia="{self.FONT_FAMILY}" w:cs="{self.FONT_FAMILY}"/>'
            '<w:color w:val="0563C1"/><w:u w:val="single"/>'
            f'<w:sz w:val="{int(size * 2)}"/>'
            "</w:rPr>"
            f'<w:t xml:space="preserve">{self._xml_escape(text)}</w:t>'
            "</w:r></w:hyperlink>"
        )
        paragraph._p.append(parse_xml(hyperlink_xml))

    def _xml_escape(self, text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    # ---------------------------------------------------------------- #
    # section heading
    # ---------------------------------------------------------------- #

    def _heading(self, doc, title: str):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(title.upper())
        self._force_font(r, size_pt=10, bold=True, color=self.COLOR_PRIMARY_RGB)

        pBdr = parse_xml(
            f'<w:pBdr {nsdecls("w")}>'
            f'<w:bottom w:val="single" w:sz="4" w:space="1" '
            f'w:color="{self.COLOR_PRIMARY_HEX}"/></w:pBdr>'
        )
        p._p.get_or_add_pPr().append(pBdr)

    # ---------------------------------------------------------------- #
    # flowing text (summary)
    # ---------------------------------------------------------------- #

    def _add_flow_text(self, doc, text: str):
        lines = self._clean_lines(text)
        if not lines:
            return
        joined = re.sub(r"\s+", " ", " ".join(lines)).strip()
        p = doc.add_paragraph(joined)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = 1.08
        for run in p.runs:
            self._force_font(run, size_pt=9.5, color=self.COLOR_BODY_RGB)

    # ---------------------------------------------------------------- #
    # education (structured)
    # ---------------------------------------------------------------- #

    def _add_education_entry(self, doc, entry: dict):
        """
        Renders one education_parsed item:
          {dates, school, degree, details[]}
        Layout:
          School                                         2022 - 2026
          Degree - honors
          extra detail lines
        """
        dates = (entry.get("dates") or "").strip()
        school = (entry.get("school") or "").strip()
        degree = (entry.get("degree") or "").strip()
        details = entry.get("details") or []

        # Peel any label that still sneaked in
        school = re.sub(r"^(College|Senior\s*High|University)\s+", "", school, flags=re.I).strip()
        degree = re.sub(r"^(College|Senior\s*High|University)\s+", "", degree, flags=re.I).strip()

        primary = school or degree
        secondary = degree if school else ""
        if not primary:
            return

        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(3)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.05
        if dates:
            p.paragraph_format.tab_stops.add_tab_stop(
                self.page_width, WD_TAB_ALIGNMENT.RIGHT
            )

        r = p.add_run(primary)
        self._force_font(r, size_pt=9.5, bold=True, color=self.COLOR_BODY_RGB)

        if dates:
            p.add_run("\t")
            r_d = p.add_run(dates)
            self._force_font(r_d, size_pt=9, color=self.COLOR_MUTED_RGB)

        if secondary:
            p2 = doc.add_paragraph()
            p2.paragraph_format.space_before = Pt(0)
            p2.paragraph_format.space_after = Pt(1)
            r2 = p2.add_run(secondary)
            self._force_font(r2, size_pt=9, italic=True, color=self.COLOR_MUTED_RGB)

        for d in details:
            d = (d or "").strip()
            if not d or self.LABEL_RE.match(d):
                continue
            pd = doc.add_paragraph()
            pd.paragraph_format.space_after = Pt(0)
            rd = pd.add_run(d)
            self._force_font(rd, size_pt=9, color=self.COLOR_BODY_RGB)

        if doc.paragraphs:
            doc.paragraphs[-1].paragraph_format.space_after = Pt(2)

    # ---------------------------------------------------------------- #
    # structured entry (experience / projects)
    # ---------------------------------------------------------------- #

    def _add_structured_entry(self, doc, entry: dict, rewritten: dict | None):
        title = (entry.get("title") or entry.get("role") or "").strip()
        subtitle = (
            entry.get("company") or entry.get("subtitle") or ""
        ).strip()
        dates = (entry.get("dates") or "").strip()
        bullets = entry.get("bullets") or []

        # Skip pure label leftovers
        if title and self.LABEL_RE.match(title) and not subtitle:
            title, subtitle = subtitle, ""
        if not title and not subtitle and not bullets:
            return

        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.05
        if dates:
            p.paragraph_format.tab_stops.add_tab_stop(
                self.page_width, WD_TAB_ALIGNMENT.RIGHT
            )

        r_title = p.add_run(title or subtitle)
        self._force_font(r_title, size_pt=9.5, bold=True, color=self.COLOR_BODY_RGB)
        if not title and subtitle:
            subtitle = ""  # already used as title

        if dates:
            p.add_run("\t")
            r_date = p.add_run(dates)
            self._force_font(r_date, size_pt=9, color=self.COLOR_MUTED_RGB)

        if subtitle and not self.LABEL_RE.match(subtitle):
            p2 = doc.add_paragraph()
            p2.paragraph_format.space_before = Pt(0)
            p2.paragraph_format.space_after = Pt(1)
            r_sub = p2.add_run(subtitle)
            self._force_font(
                r_sub, size_pt=9, italic=True, color=self.COLOR_MUTED_RGB
            )

        merged: list[str] = []
        for b in bullets:
            text = self.BULLET_RE.sub("", (b or "")).strip()
            if not text:
                continue
            if rewritten and b in rewritten:
                opt = rewritten[b]
                if (
                    isinstance(opt, dict)
                    and opt.get("ai_output")
                    and not self.PLACEHOLDER_RE.search(opt["ai_output"])
                ):
                    text = opt["ai_output"]

            # Fix: unrenderable Unicode hyphens (U+2011 etc.) from PDF/AI text
            # render as tofu boxes in DOCX viewers — normalize to ASCII.
            text = _normalize_glyphs(text)
            # FIX: Ensure missing spaces from AI rewrites or PDF gluing are patched
            text = re.sub(r"\b(platform)(using)\b", r"\1 \2", text, flags=re.I)
            text = self._split_unknown_camel_case(text)
            text = re.sub(r"\s{2,}", " ", text).strip()

            should_merge = False
            if merged:
                if text[0].islower():
                    should_merge = True
                elif re.match(
                    r"^(and|or|with|using|to|for|which|that|ensuring|"
                    r"delivering|automating|keeping|writing|wiring|"
                    r"process|collision|respond)\b",
                    text,
                    re.I,
                ):
                    should_merge = True
                elif len(text) < 50 and text.endswith("."):
                    should_merge = True

            if should_merge:
                merged[-1] += " " + text
            else:
                merged.append(text)

        for text in merged:
            bp = doc.add_paragraph(text, style="ResumeBullet")
            for run in bp.runs:
                self._force_font(run, size_pt=9.5, color=self.COLOR_BODY_RGB)

        if doc.paragraphs:
            doc.paragraphs[-1].paragraph_format.space_after = Pt(3)

    # ---------------------------------------------------------------- #
    # safe line-based fallback
    # ---------------------------------------------------------------- #

    def _add_entries(self, doc, text: str, trailing_space: bool = True):
        lines = self._clean_lines(text)
        for line in lines:
            if self.BULLET_RE.match(line):
                content = self.BULLET_RE.sub("", line).strip()
                bp = doc.add_paragraph(content, style="ResumeBullet")
                for run in bp.runs:
                    self._force_font(run, size_pt=9.5, color=self.COLOR_BODY_RGB)
                continue

            is_new_entry = bool(self.DATE_RE.match(line))
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(4) if is_new_entry else Pt(0)
            p.paragraph_format.space_after = Pt(0)
            r = p.add_run(line)
            self._force_font(
                r,
                size_pt=9.5,
                bold=is_new_entry,
                color=self.COLOR_BODY_RGB,
            )

        if trailing_space and doc.paragraphs:
            doc.paragraphs[-1].paragraph_format.space_after = Pt(4)

    def _add_list_section(self, doc, title: str, text: str):
        """Render a simple section (certifications, languages) line by line."""
        lines = self._clean_lines(text)
        if not lines:
            return
        self._heading(doc, title)
        self._add_entries(doc, "\n".join(lines), trailing_space=False)

    # ---------------------------------------------------------------- #
    # skills
    # ---------------------------------------------------------------- #

    def _add_skills(self, doc, text: str, missing_keywords: list[str] | None):
        for line in self._clean_lines(text):
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.line_spacing = 1.08
            if ":" in line:
                label, _, rest = line.partition(":")
                r_label = p.add_run(label.strip() + ": ")
                self._force_font(
                    r_label, size_pt=9.5, bold=True, color=self.COLOR_BODY_RGB
                )
                r_rest = p.add_run(rest.strip())
                self._force_font(r_rest, size_pt=9.5, color=self.COLOR_BODY_RGB)
            else:
                r = p.add_run(line)
                self._force_font(r, size_pt=9.5, color=self.COLOR_BODY_RGB)

    def _filter_keywords(
        self, skills_text: str, missing_keywords: list[str] | None
    ) -> list[str]:
        if not missing_keywords:
            return []
        out, seen = [], set()
        for kw in missing_keywords:
            cleaned = kw.strip().strip("-").strip("*").strip()
            k_lower = cleaned.lower()
            if not k_lower or k_lower in seen:
                continue
            if k_lower in skills_text.lower():
                continue
            if any(f in k_lower.split() for f in self.FLUFF):
                continue
            if not (2 < len(k_lower) < 28):
                continue
            seen.add(k_lower)
            out.append(cleaned.title())
        return out

    # ---------------------------------------------------------------- #
    # helpers
    # ---------------------------------------------------------------- #

    def _apply_rewrites(self, text: str, rewritten_bullets: dict | None) -> str:
        if not rewritten_bullets:
            return text
        for orig, ai_opt in rewritten_bullets.items():
            if (
                orig in text
                and isinstance(ai_opt, dict)
                and ai_opt.get("ai_output")
                and not self.PLACEHOLDER_RE.search(ai_opt["ai_output"])
            ):
                text = text.replace(orig, ai_opt["ai_output"])
        return _normalize_glyphs(text)

    def _split_unknown_camel_case(self, text: str) -> str:
        """Insert spaces in glued CamelCase without corrupting known tech names.

        ``JavaScript``, ``PostgreSQL``, ``MongoDB`` and friends keep their
        spelling; unknown joins such as ``WordWord`` still become
        ``Word Word`` so accidental PDF gluing remains readable.
        """
        protected_text, protected = self._protect_canonical_terms(text)
        split_text = re.sub(r"([a-z])([A-Z])", r"\1 \2", protected_text)
        return self._restore_canonical_terms(split_text, protected)

    def _protect_canonical_terms(self, text: str) -> tuple[str, list[str]]:
        protected: list[str] = []

        def replace(match: re.Match) -> str:
            protected.append(match.group(0))
            return f"\x00{len(protected) - 1}\x00"

        return TECH_TERM_RE.sub(replace, text), protected

    def _restore_canonical_terms(self, text: str, protected: list[str]) -> str:
        for index, term in enumerate(protected):
            text = text.replace(f"\x00{index}\x00", term)
        return text

    def _clean_lines(self, text: str) -> list[str]:
        if not text:
            return []
        cleaned = re.split(
            r"(?i)(?:\n\s*)?REFERENCES?\b.*", text, maxsplit=1
        )[0]
        out = []
        for ln in cleaned.splitlines():
            s = _normalize_glyphs(ln.strip())
            if not s:
                continue
            # drop pure left-column labels
            if self.LABEL_RE.match(s):
                continue
            # peel leading label on same line: "College Bachelor..." -> "Bachelor..."
            s = re.sub(
                r"^(College|Senior\s*High|Academic|Capstone|Internship)\s+",
                "",
                s,
                flags=re.I,
            ).strip()
            if s:
                out.append(s)
        return out