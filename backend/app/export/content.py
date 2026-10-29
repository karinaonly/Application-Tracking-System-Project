"""Content helpers shared by the DOCX and PDF exporters.

Both formats must show the same resume: the same sections, the same accepted
rewrites, and the same user-confirmed skills. Everything in this module is
format-agnostic text/layout work; the exporters only turn the result into
their own file format.
"""

import re

from app.common.headline import extract_headline
from app.common.skills import (
    HARD_SKILLS,
    is_soft_skill,
    label_matches_category,
    skill_category,
)


_CAMEL_BOUNDARY_RE = re.compile(r"[a-z][A-Z]")

# Glyphs that several DOCX/PDF viewers cannot render: PDF and AI output can
# smuggle in Unicode hyphen variants that show up as tofu boxes (□) in the
# exported resume. They all map to a plain ASCII hyphen. En/em dashes
# (U+2013/U+2014) are intentionally kept — Arial renders them and the parser
# uses " — " as its canonical separator.
_BAD_DASH_RE = re.compile(
    r"[\u2010\u2011\u2012\u2015\u2212\uFE58\uFE63\u00AD\uFFFD]"
)


def normalize_glyphs(text: str) -> str:
    """Replace unrenderable dash glyphs with ASCII hyphens."""
    return _BAD_DASH_RE.sub("-", text)


def normalize_layout_label(text: str) -> str:
    """Normalize a line so it can be compared against ``LAYOUT_LABELS``.

    Case, padding, a trailing colon, and hyphen-vs-space variants all collapse
    ("Part-Time:" -> "part time"), so the label set stays readable.
    """
    cleaned = (text or "").strip().rstrip(":").replace("-", " ")
    return " ".join(cleaned.lower().split())


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

# A3: confirmed keywords keep their canonical taxonomy spelling ("sql" ->
# "SQL", "javascript" -> "JavaScript") instead of the lossy .title() casing
# ("Sql") the old filter produced.
CANONICAL_SKILL_LOOKUP = {name.lower(): name for name in HARD_SKILLS}


class ResumeContentBuilder:
    """Pure content rules shared by every resume exporter.

    Subclasses render ``export_tailored``; this class owns the text
    normalization that keeps DOCX and PDF byte-for-byte consistent in what
    they say (even though the layouts differ).
    """

    DATE_RE = re.compile(r"^\d{4}(\s*[-–—]\s*\d{4})?\b")
    BULLET_RE = re.compile(r"^[•\-\*]\s*")
    PLACEHOLDER_RE = re.compile(r"\[[^\]]{1,30}\]")
    # A4: left-column labels that sometimes leak from a master-resume layout
    # (a two-column template renders "College", "Capstone", ... as their own
    # lines). This is a configurable set rather than a hardcoded regex, so a
    # different template can extend or override LAYOUT_LABELS (see
    # _is_layout_label) instead of patching a pattern.
    LAYOUT_LABELS: frozenset[str] = frozenset({
        "college", "senior high", "senior high school", "university",
        "institute", "internship", "capstone", "academic", "freelance",
        "part time", "parttime", "full time", "fulltime", "contract",
        "volunteer", "personal", "side project",
    })
    # Labels that may prefix real content on the same line ("College Bachelor
    # of Science" -> "Bachelor of Science"). Deliberately narrower than
    # LAYOUT_LABELS: an employment type like "Contract" is part of a title.
    LAYOUT_PREFIX_LABELS: frozenset[str] = frozenset({
        "college", "senior high", "senior high school", "academic",
        "capstone", "internship",
    })

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
    # whole-resume content
    # ---------------------------------------------------------------- #

    def resume_title(self, sections: dict) -> str:
        """The resume's own headline. Never the job posting's title (A4)."""
        contact = sections.get("contact_parsed", {}) or {}
        return (contact.get("title") or "").strip() or extract_headline(
            sections.get("contact", {}).get("raw", ""),
            contact.get("name", ""),
        )

    def contact_parts(self, contact: dict) -> list[tuple[str | None, str]]:
        """Contact entries as ``(link_url_or_None, display_text)``."""
        parts: list[tuple[str | None, str]] = []
        if contact.get("email"):
            parts.append((f"mailto:{contact['email']}", contact["email"]))
        if contact.get("phone"):
            parts.append((None, contact["phone"]))
        if contact.get("location"):
            parts.append((None, contact["location"]))
        for key in ("portfolio", "linkedin", "github"):
            value = contact.get(key)
            if value:
                url = value if value.startswith("http") else f"https://{value}"
                parts.append((url, value))
        return parts

    def summary_text(self, text: str) -> str:
        lines = self._clean_lines(text)
        return re.sub(r"\s+", " ", " ".join(lines)).strip()

    # ---------------------------------------------------------------- #
    # structured entries
    # ---------------------------------------------------------------- #

    def education_parts(self, entry: dict) -> dict:
        """Normalize one ``education_parsed`` item for rendering.

        Layout: School (primary) + dates, then Degree (secondary), then any
        extra detail lines. Labels that leaked from a two-column template are
        peeled off or dropped.
        """
        dates = (entry.get("dates") or "").strip()
        school = (entry.get("school") or "").strip()
        degree = (entry.get("degree") or "").strip()

        school = re.sub(
            r"^(College|Senior\s*High|University)\s+", "", school, flags=re.I
        ).strip()
        degree = re.sub(
            r"^(College|Senior\s*High|University)\s+", "", degree, flags=re.I
        ).strip()

        primary = school or degree
        secondary = degree if school else ""
        details = [
            (detail or "").strip()
            for detail in (entry.get("details") or [])
            if (detail or "").strip() and not self._is_layout_label(detail)
        ]
        return {
            "primary": primary,
            "secondary": secondary,
            "dates": dates,
            "details": details,
        }

    def entry_parts(self, entry: dict) -> dict:
        """Normalize one experience/project entry's header."""
        title = (entry.get("title") or entry.get("role") or "").strip()
        subtitle = (entry.get("company") or entry.get("subtitle") or "").strip()
        dates = (entry.get("dates") or "").strip()

        # Skip pure label leftovers
        if title and self._is_layout_label(title) and not subtitle:
            title, subtitle = subtitle, ""
        if subtitle and self._is_layout_label(subtitle):
            subtitle = ""

        return {
            "title": title or subtitle,
            "subtitle": subtitle if title else "",
            "dates": dates,
        }

    def entry_bullet_texts(
        self, bullets: list, rewritten: dict | None
    ) -> list[str]:
        """Normalized bullet text (1:1), with accepted rewrites applied.

        The exporters merge accidental continuation bullets on top of this;
        the comparison view keeps the parsed bullets 1:1 so the user can see
        exactly which line changed.
        """
        texts: list[str] = []
        for bullet in bullets:
            text = self.BULLET_RE.sub("", (bullet or "")).strip()
            if not text:
                continue
            if rewritten and bullet in rewritten:
                replacement = self._rewrite_text(rewritten[bullet])
                if replacement:
                    text = replacement

            # Unrenderable Unicode hyphens (U+2011 etc.) from PDF/AI text
            # render as tofu boxes in viewers — normalize to ASCII.
            text = normalize_glyphs(text)
            # FIX: Ensure missing spaces from AI rewrites or PDF gluing are patched
            text = re.sub(r"\b(platform)(using)\b", r"\1 \2", text, flags=re.I)
            text = self._split_unknown_camel_case(text)
            texts.append(re.sub(r"\s{2,}", " ", text).strip())
        return texts

    def entry_bullets(self, bullets: list, rewritten: dict | None) -> list[str]:
        """Apply accepted rewrites and merge accidental continuation bullets."""
        merged: list[str] = []
        for text in self.entry_bullet_texts(bullets, rewritten):
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
        return merged

    # ---------------------------------------------------------------- #
    # skills
    # ---------------------------------------------------------------- #

    def skills_lines(
        self, skills_text: str, missing_keywords: list[str] | None
    ) -> tuple[list[str], list[str]]:
        """Return ``(labeled_lines, leftover_keywords)`` for the skills section.

        Confirmed keywords fold into the matching labeled line ("Databases:
        MySQL, SQL"); anything without a matching line becomes the
        "Additional Skills" line. Soft skills never get here.
        """
        lines = self._clean_lines(skills_text)
        leftover = self._fold_keywords_into_skills(
            lines, self._filter_keywords(skills_text, missing_keywords)
        )
        return lines, leftover

    def _fold_keywords_into_skills(
        self, lines: list[str], keywords: list[str]
    ) -> list[str]:
        """Append each keyword to its matching labeled line; return leftovers."""
        leftover = []
        for kw in keywords:
            category = skill_category(kw)
            target = None
            if category:
                for index, line in enumerate(lines):
                    label, sep, _ = line.partition(":")
                    if sep and label_matches_category(label, category):
                        target = index
                        break
            if target is None:
                leftover.append(kw)
            else:
                lines[target] = self._append_skill_to_line(lines[target], kw)
        return leftover

    @staticmethod
    def _append_skill_to_line(line: str, keyword: str) -> str:
        if ":" in line:
            label, _, rest = line.partition(":")
            rest = rest.strip()
            return f"{label.strip()}: {rest + ', ' if rest else ''}{keyword}"
        return f"{line.rstrip()}, {keyword}"

    def _filter_keywords(
        self, skills_text: str, missing_keywords: list[str] | None
    ) -> list[str]:
        if not missing_keywords:
            return []
        skills_lower = skills_text.lower()
        out, seen = [], set()
        for kw in missing_keywords:
            cleaned = kw.strip().strip("-").strip("*").strip()
            k_lower = cleaned.lower()
            if not k_lower or k_lower in seen:
                continue
            # A list of soft-skill adjectives ("Innovative, Interpersonal") is
            # unverifiable and reads like keyword stuffing — they belong in
            # bullets, so they are never added to the skills list.
            if is_soft_skill(cleaned):
                continue
            # Whole-word match, not substring: "SQL" must not be considered
            # already listed just because the skills text says "MySQL" (this
            # silently dropped confirmed SQL/Java whenever MySQL/JavaScript
            # were present). Caught live on a real export.
            present = re.compile(
                r"(?<![A-Za-z0-9])" + re.escape(k_lower) + r"(?![A-Za-z0-9])"
            )
            if present.search(skills_lower):
                continue
            if any(f in k_lower.split() for f in self.FLUFF):
                continue
            if not (2 < len(k_lower) < 28):
                continue
            seen.add(k_lower)
            out.append(CANONICAL_SKILL_LOOKUP.get(k_lower, cleaned))
        return out

    # ---------------------------------------------------------------- #
    # rewrites
    # ---------------------------------------------------------------- #

    def _rewrite_text(self, opt) -> str | None:
        """Text to apply for one rewrite entry, or None to keep the original.

        Accepts either a plain string (C6: what the user accepted) or the older
        ``{"ai_output": ...}`` mapping stored on pre-C6 analyses. A rewrite with
        an unfilled ``[X]`` placeholder is never applied.
        """
        if isinstance(opt, str):
            candidate = opt.strip()
        elif isinstance(opt, dict):
            candidate = str(opt.get("ai_output") or "").strip()
        else:
            return None
        if not candidate or self.PLACEHOLDER_RE.search(candidate):
            return None
        return candidate

    def _apply_rewrites(self, text: str, rewritten_bullets: dict | None) -> str:
        if not rewritten_bullets:
            return text
        for orig, opt in rewritten_bullets.items():
            replacement = self._rewrite_text(opt)
            if replacement and orig in text:
                text = text.replace(orig, replacement)
        return normalize_glyphs(text)

    # ---------------------------------------------------------------- #
    # text normalization
    # ---------------------------------------------------------------- #

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

    def _is_layout_label(self, line: str) -> bool:
        """True when a line is only a layout tag ("College", "Capstone")."""
        return normalize_layout_label(line) in self.LAYOUT_LABELS

    def _peel_layout_label(self, line: str) -> str:
        """Strip a leading layout tag from real content."""
        for label in sorted(self.LAYOUT_PREFIX_LABELS, key=len, reverse=True):
            match = re.match(rf"^{re.escape(label)}\s+", line, re.I)
            if match:
                return line[match.end():]
        return line

    def _clean_lines(self, text: str) -> list[str]:
        if not text:
            return []
        cleaned = re.split(
            r"(?i)(?:\n\s*)?REFERENCES?\b.*", text, maxsplit=1
        )[0]
        out = []
        for ln in cleaned.splitlines():
            s = normalize_glyphs(ln.strip())
            if not s:
                continue
            # drop pure left-column labels
            if self._is_layout_label(s):
                continue
            # peel a leading label on the same line:
            # "College Bachelor of Science..." -> "Bachelor of Science..."
            s = self._peel_layout_label(s).strip()
            if s:
                out.append(s)
        return out
