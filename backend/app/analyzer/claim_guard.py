"""Heuristic guard for detecting unsupported AI resume rewrite claims.

The patterns and vocabulary are intentionally tunable heuristics, not a semantic
truth system; keep adjusting the lists as real rewrite examples reveal gaps.
"""

import re

from app.analyzer.keyword_engine import KeywordEngine
from app.common.skills import HARD_SKILLS


PLACEHOLDER_PATTERN = re.compile(
    r"\[[^\]]*\]|\{[^}]*\}|<[^>]*>|\b[Xx]{1,3}\s*%|\bN\s*%|_{3,}|\bTBD\b",
    re.I,
)

NUMBER_WORDS = {
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "twelve": 12,
}
VAGUE_QUANTITIES = {
    "dozen", "dozens", "hundred", "hundreds", "thousand", "thousands",
    "million", "millions", "double", "doubled", "triple", "tripled",
}

CLAIM_PATTERNS = {
    "automation": re.compile(r"\bautomat(?:e|es|ed|ing|ion)\b", re.I),
    "pipeline": re.compile(r"\bpipelines?\b", re.I),
    "robust": re.compile(r"\brobust(?:ly|ness)?\b", re.I),
    "guarantee": re.compile(r"\bguarant(?:ee|ees|eed|eeing)\b", re.I),
    "production-ready": re.compile(r"\bproduction[- ]ready\b", re.I),
    "scalable": re.compile(r"\bscalab(?:le|ility)\b", re.I),
    "seamless": re.compile(r"\bseamless(?:ly)?\b", re.I),
    "enterprise": re.compile(r"\benterprise(?:[- ](?:grade|level|scale))?\b", re.I),
    "streamline": re.compile(r"\bstreamlin(?:e|es|ed|ing)\b", re.I),
    "accelerate": re.compile(r"\baccelerat(?:e|es|ed|ing)\b", re.I),
    "standardize": re.compile(r"\bstandardiz(?:e|es|ed|ing)\b", re.I),
    "vague-magnitude": re.compile(
        r"\b(?:significantly|dramatically|drastically|substantially|vastly|greatly)\b", re.I
    ),
    "hype": re.compile(
        r"\b(?:mission[- ]critical|cutting[- ]edge|state[- ]of[- ]the[- ]art|world[- ]class|"
        r"best[- ]in[- ]class|high[- ]performance|zero[- ]downtime|flawless(?:ly)?)\b", re.I
    ),
}

SUPPORT_VERBS = {
    "helped", "assisted", "supported", "aided", "contributed", "participated", "worked", "collaborated",
}
HANDS_ON_VERBS = {
    "built", "developed", "implemented", "created", "wrote", "coded", "programmed", "deployed", "configured",
    "integrated", "designed", "tested", "fixed", "debugged", "maintained", "containerized", "migrated",
    "installed", "assembled", "wired", "constructed",
}
LEADERSHIP_VERBS = {"led", "managed", "directed", "oversaw", "headed", "supervised", "coordinated", "mentored", "owned"}
SENIOR_VERBS = {"architected", "spearheaded", "pioneered", "orchestrated", "championed", "revolutionized", "transformed", "overhauled", "revamped"}

_VERB_RANKS = {
    **{verb: 0 for verb in SUPPORT_VERBS},
    **{verb: 1 for verb in HANDS_ON_VERBS},
    **{verb: 2 for verb in LEADERSHIP_VERBS},
    **{verb: 2 for verb in SENIOR_VERBS},
}
_DIGIT_GROUP_RE = re.compile(r"\d+(?:[.,]\d+)*")
_WORD_RE = re.compile(r"\b[a-z]+\b", re.I)
_ENGINE = KeywordEngine()

IMPLIED_BY = {
    "API Development": {"REST API", "GraphQL", "Swagger"},
    "Authentication": {"JWT", "OAuth"},
    "Authorization": {"JWT", "OAuth"},
    "Unit Testing": {"Pytest", "Jest", "TDD"},
}

_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9+#.\-]*")


def _norm(token: str) -> str:
    return re.sub(r"[^a-z0-9]", "", token.lower())


def _looks_like_name(token: str, is_first: bool) -> bool:
    if is_first:
        return False
    core = token.strip(".-")
    return bool(
        re.match(r"[A-Z]", core)
        or re.search(r"[a-z][A-Z]", core)
        or re.search(r"[A-Za-z].*[0-9+#]", core)
        or re.search(r"\.[a-z]{2}", core)
    )


def _new_proper_nouns(original: str, rewrite: str) -> list[str]:
    original_norms = {_norm(t) for t in _TOKEN_RE.findall(original)}
    found = []
    for match in _TOKEN_RE.finditer(rewrite):
        token = match.group(0)
        # A capitalized word that starts a sentence is ordinary English, not a
        # proper noun. Summaries are multi-sentence prose, so checking only the
        # very first token flagged every new sentence ("... APIs. Focused on ...").
        before = rewrite[:match.start()].rstrip()
        sentence_start = not before or before[-1] in ".!?\n"
        if not _looks_like_name(token, sentence_start):
            continue
        norm = _norm(token)
        if not norm or norm in original_norms:
            continue
        # The prefix rule is deliberate: REST vs RESTful, NextJS vs Next.js, TailwindCSS vs Tailwind.
        if any((o.startswith(norm) or norm.startswith(o))
               for o in original_norms if len(o) >= 3 and len(norm) >= 3):
            continue
        found.append(token)
    return found


def _normal_digit(value: str) -> str:
    return value.replace(",", "")


def _violations_for_numbers(original: str, rewrite: str) -> list[str]:
    original_digits = {_normal_digit(x) for x in _DIGIT_GROUP_RE.findall(original)}
    details = []
    for value in _DIGIT_GROUP_RE.findall(rewrite):
        if _normal_digit(value) not in original_digits:
            details.append(value)

    original_words = {word.lower() for word in _WORD_RE.findall(original)}
    original_values = {int(_normal_digit(value).replace(".", "")) for value in _DIGIT_GROUP_RE.findall(original)}
    rewrite_words = {word.lower() for word in _WORD_RE.findall(rewrite)}
    for word, value in NUMBER_WORDS.items():
        if word in rewrite_words and word not in original_words and value not in original_values:
            details.append(word)
    for word in VAGUE_QUANTITIES:
        if word in rewrite_words and word not in original_words:
            details.append(word)
    return details


def _first_lead_verb(text: str) -> str | None:
    without_marker = re.sub(r"^[\s•▪▸►◆○●\-–—*]+", "", text)
    match = re.search(r"[A-Za-z]+", without_marker)
    return match.group(0).lower() if match else None


def check_rewrite(original: str, rewrite: str) -> list[tuple[str, list[str]]]:
    """Return heuristic violations found by comparing rewrite against original."""
    violations: list[tuple[str, list[str]]] = []

    original_placeholders = {match.group(0).lower() for match in PLACEHOLDER_PATTERN.finditer(original)}
    new_placeholders = [
        match.group(0) for match in PLACEHOLDER_PATTERN.finditer(rewrite)
        if match.group(0).lower() not in original_placeholders
    ]
    if new_placeholders:
        violations.append(("placeholder", new_placeholders))

    new_numbers = _violations_for_numbers(original, rewrite)
    if new_numbers:
        violations.append(("new_number", new_numbers))

    new_skills = [
        canonical for canonical in HARD_SKILLS
        if _ENGINE._contains(rewrite, canonical)
        and not _ENGINE._contains(original, canonical)
        and not (IMPLIED_BY.get(canonical, set()) & {
            skill for skill in HARD_SKILLS if _ENGINE._contains(original, skill)
        })
    ]
    if new_skills:
        violations.append(("new_skill", new_skills))

    new_claims = [
        name for name, pattern in CLAIM_PATTERNS.items()
        if pattern.search(rewrite) and not pattern.search(original)
    ]
    if new_claims:
        violations.append(("claim_word", new_claims))

    # Context claims such as "for international clients" or "under strict deadlines"
    # cannot be caught reliably by this heuristic and remain for user review (C6).
    new_names = _new_proper_nouns(original, rewrite)
    if new_names:
        violations.append(("new_proper_noun", new_names))

    original_verb = _first_lead_verb(original)
    rewrite_verb = _first_lead_verb(rewrite)
    original_rank = _VERB_RANKS.get(original_verb) if original_verb else None
    rewrite_rank = _VERB_RANKS.get(rewrite_verb) if rewrite_verb else None
    if original_rank is not None and rewrite_rank is not None and rewrite_rank >= 2 and original_rank <= 1:
        violations.append(("verb_inflation", [f"{original_verb} -> {rewrite_verb}"]))

    return violations


def describe_violations(violations: list[tuple[str, list[str]]]) -> str:
    """Create a short human-readable explanation suitable for a retry prompt."""
    descriptions = {
        "placeholder": "added placeholders",
        "new_number": "added numbers or quantities",
        "new_skill": "added skills: {}",
        "new_proper_noun": "added names or tools: {}",
        "claim_word": "added claim words: {}",
        "verb_inflation": "changed the lead verb {}",
    }
    parts = []
    for code, details in violations:
        template = descriptions.get(code, code)
        if "{}" in template:
            parts.append(template.format(", ".join(details)))
        else:
            parts.append(template)
    return "; ".join(parts) or "violated the rewrite guard"


def _clean_skill_token(token: str) -> str:
    return re.sub(r"\s+", " ", token).strip().strip(".;").strip()


def validate_skills_rewrite(
    original_skills: list[str], lines: list[str]
) -> list[str]:
    """C7: a skills rewrite may only reorganize the skills already listed.

    Every comma-separated item must match one of ``original_skills`` (case-
    insensitive), and every original skill must still be present. Category
    labels before a colon are free-form, but numbers and placeholders are
    never allowed. Returns human-readable reasons; an empty list means valid.

    Numbers inside a skill are allowed when the resume itself lists that skill
    (for example "Python 3" or "S3"): the token match below is what decides.
    """
    reasons: list[str] = []
    if not lines:
        return ["returned an empty skills section"]

    lookup = {_clean_skill_token(skill).lower(): _clean_skill_token(skill)
              for skill in original_skills if _clean_skill_token(skill)}
    if not lookup:
        return ["there are no parsed skills to reorganize"]

    found: list[str] = []
    for raw_line in lines:
        line = re.sub(r"^[\s•▪▸►◆○●*\-]+", "", str(raw_line)).strip()
        if not line:
            reasons.append("returned an empty line")
            continue
        if PLACEHOLDER_PATTERN.search(line):
            reasons.append("contains placeholders")
            continue

        body = line
        if ":" in body:
            label, _, body = body.partition(":")
            if not label.strip():
                reasons.append("has an empty category label")
                continue
            if _DIGIT_GROUP_RE.search(label):
                reasons.append("adds numbers or quantities")
                continue

        tokens = [
            _clean_skill_token(token)
            for token in body.split(",")
            if _clean_skill_token(token)
        ]
        if not tokens:
            reasons.append(f"has no skills on the line {line!r}")
            continue
        for token in tokens:
            if token.lower() not in lookup:
                reasons.append(f"adds or changes a skill: {token}")
            else:
                found.append(token.lower())

    missing = [original for key, original in lookup.items() if key not in set(found)]
    if missing:
        reasons.append("would drop skills: " + ", ".join(missing))

    # De-duplicate while preserving order; the same problem should not appear
    # five times just because a skill was repeated on several lines.
    return list(dict.fromkeys(reasons))
