import re
from collections import Counter

from app.common.skills import HARD_SKILLS, CASE_SENSITIVE, SOFT_SKILL_GROUPS

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except Exception:  # sklearn missing -> similarity is skipped, everything else still works
    TfidfVectorizer = None
    cosine_similarity = None

try:
    import spacy
    nlp = spacy.load("en_core_web_sm")
except Exception:
    nlp = None
    print("⚠️  spaCy model 'en_core_web_sm' not loaded. Extra-term suggestions are disabled. "
          "Install with: python -m spacy download en_core_web_sm")


# ---------------------------------------------------------------------------
# Matching helpers
# ---------------------------------------------------------------------------
# A term matches only when it is NOT glued to other letters/digits/dots.
#   "java"  does not match "JavaScript"
#   "js"    does not match "Node.js"
#   "c++"   and ".net" and "ci/cd" still match correctly
_LEFT = r"(?<![A-Za-z0-9.])"
_RIGHT = r"(?![A-Za-z0-9]|\.[A-Za-z0-9])"


def _compile(term: str, case_sensitive: bool = False) -> re.Pattern:
    # Flexible whitespace/hyphens between words ("problem solving" == "problem-solving")
    parts = [re.escape(p) for p in re.split(r"[\s\-]+", term.strip()) if p]
    body = r"[\s\-]+".join(parts)
    return re.compile(_LEFT + body + _RIGHT, 0 if case_sensitive else re.I)


def _build_patterns() -> dict[str, list[re.Pattern]]:
    out: dict[str, list[re.Pattern]] = {}
    for canonical, aliases in HARD_SKILLS.items():
        pats = [_compile(canonical, canonical in CASE_SENSITIVE)]
        pats += [_compile(a) for a in aliases]
        out[canonical] = pats
    for canonical, aliases in SOFT_SKILL_GROUPS.items():
        out[canonical] = [_compile(canonical)] + [_compile(alias) for alias in aliases]
    return out


_SKILL_PATTERNS = _build_patterns()
_SOFT_NAMES = set(SOFT_SKILL_GROUPS)

# Noun-chunk junk filters (only used for the optional "other terms" list)
_GENERIC_WORDS = {
    "team", "teams", "company", "role", "roles", "job", "position", "candidate", "candidates",
    "experience", "experiences", "skill", "skills", "ability", "abilities", "requirement",
    "requirements", "responsibility", "responsibilities", "qualification", "qualifications",
    "opportunity", "opportunities", "work", "people", "environment", "years", "year", "plus",
    "benefit", "benefits", "salary", "location", "day", "time", "things", "thing", "way",
    "knowledge", "understanding", "someone", "something", "everyone", "organization",
}
_PRONOUNS = {"we", "you", "your", "our", "us", "they", "them", "their", "who", "what", "this", "that", "it", "i"}

MIN_SCORABLE_SKILLS = 3  # below this, a keyword score would be meaningless


class KeywordEngine:
    def analyze(self, resume_text: str, jd_text: str) -> dict:
        jd_skills = self._extract_skills(jd_text)          # ranked list of (name, count_in_jd)
        details, matched, missing = [], [], []
        for name, count in jd_skills:
            in_resume = self._contains(resume_text, name)
            details.append({"skill": name, "jd_mentions": count, "in_resume": in_resume})
            (matched if in_resume else missing).append(name)

        available = len(jd_skills) >= MIN_SCORABLE_SKILLS
        score = round(len(matched) / len(jd_skills) * 100, 1) if available else None

        other_terms = self._extract_other_terms(jd_text, exclude={n.lower() for n, _ in jd_skills})
        missing_other = [t for t in other_terms if not self._contains_plain(resume_text, t)]

        # A3: soft skills are only advice — they must not be listed in a
        # skills section (a list of adjectives is unverifiable and reads like
        # keyword stuffing), so the UI shows them separately.
        soft_missing = [name for name in missing if name in _SOFT_NAMES]

        return {
            "score": score,                        # None => not enough recognizable skills in the JD
            "score_available": available,
            "reason": None if available else (
                f"Only {len(jd_skills)} recognizable skill(s) found in the job description. "
                "Paste the full description, or extend the skills list."
            ),
            "similarity": self._similarity(resume_text, jd_text),
            "total_jd_keywords": len(jd_skills),
            "matched_keywords": matched,           # ranked by how often the JD mentions them
            "missing_keywords": missing,
            "soft_missing_keywords": soft_missing, # informational only, never added to skills
            "keyword_details": details,
            "other_terms_missing": missing_other,  # informational only, NOT part of the score
        }

    # ------------------------------------------------------------------ #
    def _contains(self, text: str, canonical: str) -> bool:
        pats = _SKILL_PATTERNS.get(canonical)
        return bool(pats) and any(p.search(text) for p in pats)

    def _contains_plain(self, text: str, term: str) -> bool:
        return bool(_compile(term).search(text))

    def _count(self, text: str, canonical: str) -> int:
        # Count non-overlapping mentions across all spellings of a skill
        spans: list[tuple[int, int]] = []
        for p in _SKILL_PATTERNS[canonical]:
            spans += [m.span() for m in p.finditer(text)]
        spans.sort()
        n, last_end = 0, -1
        for s, e in spans:
            if s >= last_end:
                n += 1
                last_end = e
        return n

    def _first_pos(self, text: str, canonical: str) -> int:
        hits = [m.start() for p in _SKILL_PATTERNS[canonical] for m in [p.search(text)] if m]
        return min(hits) if hits else 10**9

    def _extract_skills(self, text: str, limit: int = 40) -> list[tuple[str, int]]:
        """Deterministic: ranked by JD frequency (desc), hard skills before soft on ties, then first appearance."""
        found = []
        for name in _SKILL_PATTERNS:
            c = self._count(text, name)
            if c:
                found.append((name, c, self._first_pos(text, name), name in _SOFT_NAMES))
        found.sort(key=lambda x: (-x[1], x[3], x[2], x[0]))
        return [(n, c) for n, c, _, _ in found[:limit]]

    def _extract_other_terms(self, text: str, exclude: set[str], limit: int = 12) -> list[str]:
        """Optional: noun phrases not in the taxonomy, filtered hard to avoid junk like 'the team'."""
        if not nlp:
            return []
        counts: Counter = Counter()
        first_seen: dict[str, int] = {}
        for chunk in nlp(text).noun_chunks:
            toks = [t for t in chunk if not (t.is_stop or t.is_punct or t.like_num)]
            if not toks or any(t.lower_ in _PRONOUNS for t in chunk):
                continue
            phrase = " ".join(t.text for t in toks).strip()
            low = phrase.lower()
            words = low.split()
            if not (3 <= len(phrase) <= 30) or len(words) > 3:
                continue
            if all(w in _GENERIC_WORDS for w in words) or low in exclude:
                continue
            if not any(t.pos_ in ("NOUN", "PROPN") for t in toks):
                continue
            counts[low] += 1
            first_seen.setdefault(low, chunk.start_char)
        ranked = sorted(counts, key=lambda k: (-counts[k], first_seen[k], k))
        return ranked[:limit]

    def _similarity(self, resume_text: str, jd_text: str) -> float:
        if not TfidfVectorizer:
            return 0.0
        try:
            vec = TfidfVectorizer(stop_words="english")
            mat = vec.fit_transform([resume_text, jd_text]).toarray()
            return round(float(cosine_similarity(mat[0:1], mat[1:2])[0][0]) * 100, 1)
        except Exception:
            return 0.0
