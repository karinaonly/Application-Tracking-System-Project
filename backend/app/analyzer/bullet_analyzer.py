import re
from app.common.constants import WEAK_VERBS, WEAK_TO_STRONG, is_strong_action_verb
from app.common.skills import HARD_SKILLS

_BULLET_PREFIX_RE = re.compile(r"^[\s•▪▸►◆○●\-–—*]+")

# Weak phrases are only weak when the bullet STARTS with them, and only as whole words.
# (Old logic did `phrase in bullet[:20]`, so "Candidate..." matched "did" and "Shadow..." matched "had".)
# Longest phrases first so "was responsible for" wins over "responsible for".
_WEAK_START_RE = re.compile(
    r"^(" + "|".join(re.escape(w) for w in sorted(WEAK_VERBS, key=len, reverse=True)) + r")\b",
    re.I,
)

_DEFAULT_REPLACEMENTS = ["Spearheaded", "Led", "Engineered"]
_TECH_TERMS = {term.lower() for canonical, aliases in HARD_SKILLS.items() for term in [canonical, *aliases]}
_QUANTITY_NOUNS = (
    "member(?:s)?|person|people|user(?:s)?|client(?:s)?|endpoint(?:s)?|table(?:s)?|"
    "project(?:s)?|service(?:s)?|module(?:s)?|page(?:s)?|feature(?:s)?|week(?:s)?|"
    "month(?:s)?|day(?:s)?|hour(?:s)?|million|billion|thousand|hundred"
)
_QUANTITY_CONTEXT_RE = re.compile(
    rf"(?:\s*-\s*|\s+)(?:[A-Za-z][\w.+#/-]*\s+)*(?:{_QUANTITY_NOUNS})\b",
    re.I,
)
_MAGNITUDE_SUFFIX_RE = re.compile(r"[kmbx]$", re.I)
_VERSION_WORD_RE = re.compile(r"^(?:v(?:er(?:sion)?)?)$", re.I)
_MONEY_RE = re.compile(r"(?:[$₱]\s*|PHP\s+)[\d,]+(?:\.\d+)?[kmb]?\b", re.I)
_PERCENT_RE = re.compile(r"(?<![A-Za-z0-9.])\d+(?:\.\d+)?\s*%")
_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9.])(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:[kmbx])?(?![A-Za-z0-9]|\.[A-Za-z0-9])",
    re.I,
)
# A11: a phone number in a bullet ("Reachable at +63 917 234 5678") is not an
# impact metric. The pattern matches a run of digits/separators, and a span
# must contain at least 7 digits so short quantities ("50 000") are not
# mistaken for phone numbers.
_PHONE_RE = re.compile(r"(?<!\w)\+?\d[\d\s().-]{5,}\d(?!\w)")
_PHONE_MIN_DIGITS = 7


def _phone_spans(text: str) -> list[tuple[int, int]]:
    return [
        (match.start(), match.end())
        for match in _PHONE_RE.finditer(text)
        if len(re.sub(r"\D", "", match.group(0))) >= _PHONE_MIN_DIGITS
    ]


def _previous_word(text: str, start: int) -> str:
    match = re.search(r"([A-Za-z][A-Za-z0-9+.#/-]*)\s*$", text[:start])
    return match.group(1).lower() if match else ""


def _is_technology_version(text: str, match: re.Match[str]) -> bool:
    """A16: a decimal is only a version in a tech context -- `2.5x` metrics count."""
    value = match.group(0)
    numeric = re.sub(r"[kmbx]$", "", value, flags=re.I)
    if re.fullmatch(r"(?:19|20)\d{2}", numeric):
        return True
    previous = _previous_word(text, match.start())
    if previous in _TECH_TERMS or _VERSION_WORD_RE.match(previous):
        return True
    # An explicit magnitude suffix is a quantity ("2.5x", "3k users"), never a version.
    if _MAGNITUDE_SUFFIX_RE.search(value):
        return False
    if "." in numeric:
        # No suffix: a decimal is a metric when a quantity/magnitude word follows
        # ("3.5 hours", "1.5 million users"); otherwise treat it as a version.
        return not _QUANTITY_CONTEXT_RE.match(text[match.end():])
    return False


def _extract_metrics(text: str) -> list[str]:
    matches: list[tuple[int, str]] = []
    phone_spans = _phone_spans(text)

    def in_phone(pos: int) -> bool:
        return any(start <= pos < end for start, end in phone_spans)

    for match in _MONEY_RE.finditer(text):
        value = match.group(0)
        amount = re.search(r"[\d,]+(?:\.\d+)?", value)
        if value.lower().startswith("php") and amount and len(re.sub(r"\D", "", amount.group(0))) == 1:
            continue
        matches.append((match.start(), value))
    matches.extend((match.start(), match.group(0)) for match in _PERCENT_RE.finditer(text))

    for match in _NUMBER_RE.finditer(text):
        value = match.group(0)
        if in_phone(match.start()):
            continue
        if _is_technology_version(text, match):
            continue
        suffix = value[-1].lower() if value[-1].isalpha() else ""
        digits = re.sub(r"\D", "", value)
        if len(digits) == 1 and not suffix:
            following = text[match.end():]
            if not re.match(rf"(?:\s*-\s*|\s+)(?:[A-Za-z][\w.+#/-]*\s+)*(?P<quantity>{_QUANTITY_NOUNS})\b", following, re.I):
                continue
        matches.append((match.start(), value))

    return [value for _, value in sorted(matches)]


class BulletAnalyzer:
    def analyze_bullets(self, exp_entries: list) -> dict:
        total = 0
        with_metrics = 0
        strong_verbs = 0
        weak_verbs = 0
        bullet_reports = []

        for entry in exp_entries:
            for b in entry.get("bullets", []):
                total += 1
                b_res = self._check_bullet(b, entry.get("_section", "Experience"))
                if b_res["has_metrics"]: with_metrics += 1
                if b_res["verb_type"] == "strong": strong_verbs += 1
                if b_res["verb_type"] == "weak": weak_verbs += 1
                bullet_reports.append(b_res)

        # No bullets => we cannot judge. Do NOT return a perfect score for a resume
        # whose parsing failed.
        if total == 0:
            return {
                "score": None,
                "score_available": False,
                "warning": "No bullet points detected in Experience/Projects. "
                           "The resume may be formatted in a way the parser can't read.",
                "total_bullets": 0,
                "bullets_with_metrics": 0,
                "strong_verbs_count": 0,
                "weak_verbs_count": 0,
                "details": [],
            }

        metric_ratio = with_metrics / total
        verb_ratio = strong_verbs / total
        score = round((metric_ratio * 50) + (verb_ratio * 50), 1)

        return {
            "score": score,
            "score_available": True,
            "warning": None,
            "total_bullets": total,
            "bullets_with_metrics": with_metrics,
            "strong_verbs_count": strong_verbs,
            "weak_verbs_count": weak_verbs,
            "details": bullet_reports,
        }

    def _check_bullet(self, bullet: str, section: str) -> dict:
        text = _BULLET_PREFIX_RE.sub("", bullet or "")
        words = text.split()
        first_clean = re.sub(r"[^a-z]", "", words[0].lower()) if words else ""

        verb_type = "missing"
        suggestion = ""

        weak_match = _WEAK_START_RE.match(text)
        if is_strong_action_verb(first_clean):
            verb_type = "strong"
        elif weak_match:
            verb_type = "weak"
            reps = [r.capitalize() for r in WEAK_TO_STRONG.get(weak_match.group(1).lower(), _DEFAULT_REPLACEMENTS)]
            suggestion = f"Replace with: {', '.join(reps)}"

        metrics = _extract_metrics(bullet or "")

        return {
            "original": bullet,
            "section": section,
            "verb_type": verb_type,
            "has_metrics": len(metrics) > 0,
            "metrics": metrics,
            "suggestion": suggestion,
        }
