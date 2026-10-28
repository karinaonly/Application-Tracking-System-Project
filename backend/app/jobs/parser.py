"""D2: deterministic job-description parser.

Runs once on save and stores the result in `JobDescription.extracted_keywords`:
required skills, preferred skills, other mentions, tools, seniority, and the
minimum years of experience. No AI involved -- fully testable and free.

Skills are recognized with the same curated taxonomy the keyword engine uses,
so "required skills" here are exactly the terms the keyword score can match.
"""

import re

from app.analyzer.keyword_engine import _SKILL_PATTERNS

# Section headers that switch which bucket following lines fall into.
_REQUIRED_HEADER_RE = re.compile(
    r"(?i)\b(?:requirements?|required|qualifications|minimum\s+qualifications|"
    r"basic\s+qualifications|must[- ]haves?|what\s+you.?ll\s+need|what\s+we.?re\s+looking\s+for|"
    r"who\s+you\s+are|about\s+you|you\s+have|essential|skills\s+(?:and\s+)?(?:experience\s+)?required)\b"
)
_PREFERRED_HEADER_RE = re.compile(
    r"(?i)\b(?:preferred(?:\s+qualifications)?|nice\s+to\s+have|good\s+to\s+have|"
    r"bonus(?:\s+points)?|plus(?:es)?|desirable|additional\s+(?:skills|qualifications)|"
    r"would\s+be\s+a\s+plus|advantageous)\b"
)

# A header line is short and stands alone (often ends with ':', may be ALL CAPS).
_HEADER_LINE_MAX_LEN = 80
_HEADER_MAX_WORDS = 5
_HEADER_KEYWORD_WINDOW = 30  # the header keyword must appear this close to the line start
_BULLET_PREFIX_RE = re.compile(r"^(?:[-•*▪▸>]+\s+)+")

# Headers that end a requirements/preferred block (benefits, company blurb, ...)
_NEUTRAL_HEADER_RE = re.compile(
    r"(?i)\b(?:benefits|perks|compensation|what\s+we\s+offer|about\s+(?:us|the\s+company|the\s+team)|"
    r"equal\s+opportunity|why\s+join|our\s+benefits)\b"
)

_SENIORITY_WORDS = [
    # (canonical, pattern) — first match on the title wins, then the body.
    # The body fallback deliberately excludes "manager"/"lead"/"director":
    # a JD that *mentions* a project manager is not a manager job.
    ("intern", r"\bintern(?:ship)?\b"),
    ("junior", r"\b(?:junior|jr\.?|entry[- ]level|graduate|trainee)\b"),
    ("mid-level", r"\b(?:mid[- ]level|intermediate)\b"),
    ("senior", r"\b(?:senior|sr\.?)\b"),
    ("lead", r"\b(?:tech\s+lead|team\s+lead)\b"),
    ("principal", r"\b(?:principal|staff)\b"),
    ("manager", r"\b(?:engineering\s+manager|head\s+of|director)\b"),
]

_BODY_SENIORITY_WORDS = _SENIORITY_WORDS[:4]  # intern/junior/mid/senior only

_YEARS_RE = re.compile(r"(?i)(\d+)\s*\+?\s*(?:to\s*\d+\s*\+?\s*)?years?(?:\s+of)?(?:\s+\w+){0,3}\s+experience")
_YEARS_SIMPLE_RE = re.compile(r"(?i)(\d+)\s*\+?\s*years?\b")

# Taxonomy members that are tools/infrastructure/collaboration software rather
# than languages or frameworks. Curated on purpose -- deriving it from the
# skills.py section comments would be fragile.
_TOOLS = frozenset({
    "AWS", "Azure", "GCP",
    "Docker", "Kubernetes", "Terraform", "Ansible", "Jenkins", "GitHub Actions",
    "Git", "GitHub", "GitLab", "Nginx", "Linux", "Serverless",
    "Jira", "Figma", "Confluence", "Swagger", "Postman", "Vite",
    "PostgreSQL", "MySQL", "SQLite", "MongoDB", "Redis", "Firebase", "Supabase",
    "Elasticsearch", "SQL Server", "Oracle",
    "Tableau", "Power BI", "Excel", "Salesforce",
})


def _find_skill(text: str, canonical: str) -> bool:
    return any(p.search(text) for p in _SKILL_PATTERNS.get(canonical, []))


def _is_header(line: str, pattern: re.Pattern) -> bool:
    """A section header is a SHORT line whose keyword sits near the start —
    content lines like '- Kubernetes and Terraform experience is a plus' must
    never switch sections just because they contain the word 'plus'. For
    inline headers ('Requirements: Python, Docker') only the label before the
    colon counts toward the length/word limits."""
    stripped = _BULLET_PREFIX_RE.sub("", line.strip()).strip()
    label = stripped.split(":", 1)[0].strip() if ":" in stripped else stripped.rstrip(":").strip()
    if not label or len(label) > _HEADER_LINE_MAX_LEN:
        return False
    if len(label.split()) > _HEADER_MAX_WORDS:
        return False
    return bool(pattern.search(label[:_HEADER_KEYWORD_WINDOW]))


def _remainder_after_colon(line: str) -> str:
    """Content following an inline header colon ('Requirements: Python')."""
    if ":" not in line:
        return ""
    return line.split(":", 1)[1].strip()


class JobParser:
    def parse(self, raw_text: str, title: str = "") -> dict:
        buckets = self._split_sections(raw_text)
        skills = self._extract_skills(buckets)
        return {
            **skills,
            "tools": sorted(s for s in skills["required_skills"] + skills["preferred_skills"] + skills["other_skills"]
                            if s in _TOOLS),
            "seniority": self._detect_seniority(title, raw_text),
            "min_years_experience": self._detect_min_years(raw_text),
        }

    def _split_sections(self, raw_text: str) -> dict[str, list[str]]:
        """Assign each JD line to required / preferred / other by section headers.
        An inline header ('Requirements: Python, Docker') feeds its remainder
        into the new bucket instead of dropping it."""
        buckets: dict[str, list[str]] = {"required": [], "preferred": [], "other": []}
        current = "other"
        for line in (raw_text or "").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if _is_header(stripped, _NEUTRAL_HEADER_RE) and not _REQUIRED_HEADER_RE.search(stripped):
                current = "other"
            elif _is_header(stripped, _PREFERRED_HEADER_RE) and not _REQUIRED_HEADER_RE.search(stripped):
                current = "preferred"
            elif _is_header(stripped, _REQUIRED_HEADER_RE):
                current = "required"
            else:
                buckets[current].append(stripped)
                continue
            remainder = _remainder_after_colon(stripped)
            if remainder:
                buckets[current].append(remainder)
        return buckets

    def _extract_skills(self, buckets: dict[str, list[str]]) -> dict[str, list[str]]:
        # A skill lands in the strictest bucket where it appears: required
        # beats preferred beats other.
        texts = {name: "\n".join(lines) for name, lines in buckets.items()}
        out = {"required_skills": [], "preferred_skills": [], "other_skills": []}
        for canonical in _SKILL_PATTERNS:
            if _find_skill(texts["required"], canonical):
                out["required_skills"].append(canonical)
            elif _find_skill(texts["preferred"], canonical):
                out["preferred_skills"].append(canonical)
            elif _find_skill(texts["other"], canonical):
                out["other_skills"].append(canonical)
        return out

    def _detect_seniority(self, title: str, raw_text: str) -> str:
        for canonical, pattern in _SENIORITY_WORDS:
            if re.search(pattern, title or "", re.I):
                return canonical
        for canonical, pattern in _BODY_SENIORITY_WORDS:
            # Body words are weaker evidence; only scan the first part of the JD
            if re.search(pattern, (raw_text or "")[:600], re.I):
                return canonical
        return "unspecified"

    def _detect_min_years(self, raw_text: str) -> int | None:
        text = raw_text or ""
        match = _YEARS_RE.search(text)
        if not match:
            match = _YEARS_SIMPLE_RE.search(text)
        if not match:
            return None
        try:
            years = int(match.group(1))
        except ValueError:
            return None
        return years if 0 < years <= 20 else None
