"""Shared patterns and text helpers for the section parsers.

Everything here is stateless: the regexes are compiled once at import time and
the functions take plain strings. Section-specific parsing lives in the sibling
modules (`contact`, `experience`, `projects`, `education`, `skills`) so each
layout rule can be read and tested on its own.
"""
import re


# Left-column tags from the master resume layout — never real content
LABEL_RE = re.compile(
    r"^(?:College|Senior\s*High(?:\s*School)?|University|Institute|"
    r"Internship|Capstone|Academic|Freelance|Part[- ]?Time|"
    r"Full[- ]?Time|Contract|Volunteer|Personal|Side\s*Project)$",
    re.I,
)
DATE_RE = re.compile(
    r"(?P<dates>"
    r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?"
    r"(?:20|19)\d{2}"
    r"(?:\s*[-–—to]+\s*"
    r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?"
    r"(?:(?:20|19)\d{2}|Present|Current))?"
    r")",
    re.I,
)
BULLET_RE = re.compile(r"^[•▪▸►◆○●\-–—*]\s+")
ACTION_RE = re.compile(
    r"^(built|led|implemented|deployed|managed|collaborated|developed|"
    r"created|designed|optimized|automated|integrated|handled|wrote|"
    r"improved|participated|maintained|configured|architected)\b",
    re.I,
)
# "Backend Developer Intern at Synchores Information"
ROLE_AT_CO_RE = re.compile(
    r"^(?P<title>.+?)\s+\bat\b\s+(?P<company>.+)$",
    re.I,
)
# A15: per-field contact patterns. Lines are parsed field-by-field, so a
# line that contains an email/phone/URL is never treated as the name.
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(
    r"(?<![\w.])(?:\+?\d{1,3}[\s\-]?)?(?:\(?\d{2,4}\)?[\s\-]?)\d{3,4}[\s\-]?\d{3,4}(?![\w.])"
)
LINKEDIN_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?linkedin\.com/in/[a-zA-Z0-9\-_]+", re.I
)
GITHUB_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/[a-zA-Z0-9\-]+", re.I
)
GENERIC_URL_RE = re.compile(
    r"(?:https?://[^\s,;]+|www\.[^\s,;]+|"
    # F4: \b after the TLD — without it, "carlos.mendoza" matches as the
    # fake domain "carlos.me" (the "me" TLD eats the first two letters of
    # the next word), and emails sprouted phantom portfolio fields.
    r"(?<!@)\b[\w\-]+\.(?:com|dev|io|net|org|app|me|ai|co|ph)\b(?:/[^\s,;]*)?)",
    re.I,
)
LABELED_FIELD_RE = re.compile(
    r"^(?P<key>linkedin|github|portfolio|website|email|phone|mobile|tel|location|address)\s*[:\-–—]\s*(?P<value>.+)$",
    re.I,
)
# A whole short line that looks like "City, Province" (optionally + postal code)
LOCATION_LINE_RE = re.compile(
    r"^[A-Z][A-Za-z.\s'\-]*,\s*[A-Z][A-Za-z.\s'\-]*?(?:\s+\d{4,6})?$"
)
ROLE_LINE_RE = re.compile(r"(developer|engineer|student|intern)", re.I)

# A15: inline section headers like "Skills: Python, JavaScript, React"
INLINE_HEADER_RE = re.compile(
    r"^(?P<label>[A-Za-z][A-Za-z\s/&]*?)\s*[:\u2013\u2014]\s*(?P<rest>\S.*)$"
)

# F4: involvement-type headers (org names, roles, tutor lines) carry no
# resume data the analyzers use — left in place they leak into whatever
# section precedes them, usually PROJECTS ("THETA MU SOCIETY" became a
# fake project entry). Skipped entirely, like REFERENCES.
SKIPPED_HEADER_RE = re.compile(
    r"(?i)^(?:(?:extracurricular|community|campus|student)\s+)?"
    r"(?:activities|involvement|organizations?|affiliations?|leadership|volunteer(?:ing)?)"
    r"(?:\s+(?:and|&)\s+(?:activities|involvement|leadership|organizations?))?$"
)

REFERENCES_RE = re.compile(r"(?i)\n?\s*REFERENCES?\b.*")


def is_label(line: str) -> bool:
    return bool(LABEL_RE.match(line.strip()))


def is_skipped_header(line: str) -> bool:
    cleaned = re.sub(r"[:\-_=|#*•]+", "", line).strip()
    return bool(SKIPPED_HEADER_RE.match(cleaned))


def is_date_only(line: str) -> bool:
    s = line.strip()
    m = DATE_RE.fullmatch(s) or DATE_RE.fullmatch(
        re.sub(r"[\s\|•\-–—]+$", "", s)
    )
    return m is not None


def strip_date(line: str) -> tuple[str, str]:
    """Return (dates, rest). dates='' if none."""
    m = DATE_RE.search(line)
    if not m:
        return "", line.strip(" |-–—")
    dates = m.group("dates").strip()
    rest = (line[: m.start()] + line[m.end() :]).strip(" |-–—,")
    return dates, rest


def split_role_at_company(text: str) -> tuple[str, str]:
    m = ROLE_AT_CO_RE.match(text.strip())
    if m:
        return m.group("title").strip(), m.group("company").strip()
    return text.strip(), ""


def clean_company(text: str) -> str:
    """Remove left-column label words that leaked into company/meta strings."""
    if not text:
        return ""
    # PDF extraction can turn the "|" separator glyph into a capital "I"
    # ("486-Hour | Imus, Cavite" arrives as "486-Hour I Imus, Cavite").
    # Restore it only between a word and a capitalized word.
    text = re.sub(r"(?<=\w)\s+I\s+(?=[A-Z])", " | ", text)
    # Remove standalone label tokens anywhere in the string
    text = re.sub(
        r"\b(?:Internship|Capstone|Academic|College|Freelance|Volunteer)\b",
        "",
        text,
        flags=re.I,
    )
    # Collapse leftover separators. A hyphen INSIDE a compound ("486-Hour",
    # "Full-Stack") is never a separator -- only a hyphen surrounded by
    # spaces is; em/en dashes always are.
    text = re.sub(r"\s*[—–]\s*", " — ", text)
    text = re.sub(r"(?:(?<=\s)|^)-(?:(?=\s)|$)", " — ", text)
    text = re.sub(r"\s*[|]\s*", " | ", text)
    text = re.sub(r"(?:\s*\|\s*){2,}", " | ", text)
    text = re.sub(r"(?:\s*—\s*){2,}", " — ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip(" |—–- \t")


def clean_degree(text: str) -> str:
    """Strip left-column label leakage from a degree line — without eating
    school names (A15: 'University of the Philippines' must survive)."""
    if not text:
        return ""
    # Two-column PDFs can duplicate the label: "Senior High Senior High School, ..."
    text = re.sub(
        r"^(?P<label>Senior\s*High(?:\s*School)?)\s+(?P=label)\b",
        r"\g<label>",
        text,
        flags=re.I,
    )
    # A left-column label merged in front of the real degree token:
    # "College Bachelor of Science in ..." -> "Bachelor of Science in ..."
    text = re.sub(
        r"^(?:College|Senior\s*High(?:\s*School)?|University|Institute|School|Academy)\b"
        r"\s*(?:[,:\u2013\u2014\u00b7-]\s*)?"
        r"(?=(?:Bachelor|Master|Doctor|Ph\.?D|B\.?S\.?c?\.?|B\.?A\.?|M\.?S\.?|M\.?A\.?|"
        r"Senior\s*High\s*School|Diploma|Certificate|GPA|GWA)\b)",
        "",
        text,
        flags=re.I,
        count=1,
    )
    # Separator-attached label: "School, ABM Strand", "Senior High, ABM Strand".
    # Note "Senior High School, ABM Strand" is real degree content and is kept.
    text = re.sub(
        r"^(?:College|Senior\s*High|University|Institute|School)\b\s*[,:\u2013\u2014\u00b7]\s*",
        "",
        text,
        flags=re.I,
        count=1,
    )
    # Label-only lines collapse to ""
    text = re.sub(
        r"^(?:College|Senior\s*High(?:\s*School)?|University|Institute|School)$",
        "",
        text,
        flags=re.I,
    ).strip()
    # If we stripped too hard and left a leading comma
    text = text.lstrip(", ").strip()
    return text


def strip_references(raw: str) -> str:
    """Drop a REFERENCES section that was glued onto the end of another one."""
    return re.split(REFERENCES_RE, raw, maxsplit=1)[0].strip()
