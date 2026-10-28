"""Detect a resume's own professional headline ("FULL STACK DEVELOPER").

A4: the contact block's second line -- the candidate's professional title --
used to be discarded, because it is neither the name nor a contact field. The
exporter then had to invent one: it substituted the attached job's title
silently, or fell back to a hardcoded "FULL STACK DEVELOPER" that only matched
one person's resume.

We now read the title out of the header itself and never make one up. The
heuristic is intentionally narrow (it only accepts a short line that names a
role), because a false positive would print a degree or a city as the title.
"""

import re

_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}")
_URL_RE = re.compile(r"(?:https?://|www\.|\bgithub\.com\b|\blinkedin\.com\b)", re.I)
# A headline never contains a phone number, postal code, or graduation year.
_DIGIT_RE = re.compile(r"\d")
_LABELED_FIELD_RE = re.compile(
    r"^(?:linkedin|github|portfolio|website|email|phone|mobile|tel|location|address)"
    r"\s*[:\-–—]",
    re.I,
)
# "Bacoor City, Cavite" / "Cebu City 6000"
_LOCATION_RE = re.compile(
    r"^[A-Z][A-Za-z.\s'\-]*,\s*[A-Z][A-Za-z.\s'\-]*?(?:\s+\d{4,6})?$"
)
# Degrees are credentials, not a professional title.
_DEGREE_RE = re.compile(
    r"\b(?:bs|b\.s\.|ba|b\.a\.|bsc|msc|ms|m\.s\.|bachelor|bachelors|master|"
    r"masters|phd|ph\.d\.|diploma|associate)\b",
    re.I,
)
# Words that make a line look like a job title rather than stray header noise.
_ROLE_RE = re.compile(
    r"\b(?:developer|engineer|programmer|analyst|designer|architect|"
    r"administrator|consultant|specialist|manager|director|coordinator|"
    r"officer|associate|intern|student|teacher|instructor|professor|"
    r"scientist|technician|strategist|researcher|accountant|nurse|writer|"
    r"editor|marketer|representative|assistant|supervisor|lead|owner|"
    r"founder|freelancer)\b",
    re.I,
)

MAX_HEADLINE_CHARS = 60
MAX_HEADLINE_WORDS = 8


def looks_like_headline(line: str) -> bool:
    """True when a stripped header line could be the candidate's title."""
    if not line or len(line) > MAX_HEADLINE_CHARS:
        return False
    if len(line.split()) > MAX_HEADLINE_WORDS:
        return False
    if _EMAIL_RE.search(line) or _URL_RE.search(line):
        return False
    if _LABELED_FIELD_RE.match(line) or _DIGIT_RE.search(line):
        return False
    if _LOCATION_RE.match(line) or _DEGREE_RE.search(line):
        return False
    return bool(_ROLE_RE.search(line))


def extract_headline(raw: str, name: str = "") -> str:
    """Return the professional title from a contact block, or "".

    ``raw`` is the resume's header/contact text; ``name`` is skipped so the
    candidate's own name is never mistaken for a title.
    """
    if not raw:
        return ""
    name_norm = " ".join((name or "").split()).lower()
    for raw_line in raw.splitlines():
        line = " ".join(raw_line.split())
        if not line:
            continue
        if name_norm and line.lower() == name_norm:
            continue
        if looks_like_headline(line):
            return line
    return ""
