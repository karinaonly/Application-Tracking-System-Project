import re

from spellchecker import SpellChecker

from app.common.skills import HARD_SKILLS

# A8: extract words independently of punctuation, so "system," and "(API)"
# are checked instead of being skipped by an `isalpha()` filter. Hyphens,
# dots and slashes split words ("problem-solving" -> "problem", "solving"),
# while apostrophes stay inside contractions ("don't", "team's").
_WORD_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*")

# Common resume/tech vocabulary that is not a typo. The taxonomy covers most
# skill names; this fills in the everyday acronyms around them.
_EXTRA_WORDS = [
    "api", "apis", "sql", "rest", "restful", "json", "xml", "html", "css",
    "http", "https", "url", "uri", "cli", "sdk", "orm", "crud", "ui", "ux",
    "ide", "ci", "cd", "qa", "oauth", "jwt", "aws", "gcp", "devops",
    "frontend", "backend", "fullstack", "github", "linkedin", "fastapi",
    "docker", "kubernetes", "sqlmodel", "microservices", "cicd", "nosql",
    "postgres", "postgresql", "mysql", "mongodb", "redis", "graphql",
    "javascript", "typescript", "nodejs", "react", "vue", "angular",
    "django", "flask", "pytest", "pandas", "numpy", "scikit", "sklearn",
    "pytorch", "tensorflow", "jenkins", "terraform", "ansible", "nginx",
    # Everyday resume abbreviations and Latin honors.
    "app", "apps", "dev", "devs", "dl", "gmail", "vercel", "cum", "laude",
    "magna", "summa",
]

# Every single-token skill name/alias is known, so "FastAPI" or "Kubernetes"
# is never reported as a typo. Multi-word skills are irrelevant here because
# the tokenizer only produces single words.
_KNOWN_TECH = {
    term.lower()
    for canonical, aliases in HARD_SKILLS.items()
    for term in [canonical, *aliases]
}
_KNOWN_TECH |= set(_EXTRA_WORDS)

# A8: resumes are full of proper nouns (companies, schools, people) and
# acronyms that a general dictionary does not know. Reporting those as typos
# with invented corrections is worse than saying nothing, so a capitalized
# word is only checked at the start of a sentence/line; all-caps acronyms and
# mixed-case names (NestJS, TypeORM) are always skipped.
_SENTENCE_END = ".!?:;\n•-–—*"


def _is_proper_noun(text: str, match: re.Match[str]) -> bool:
    raw = match.group(0)
    if len(raw) > 1 and raw.isupper():
        return True
    if raw[1:] != raw[1:].lower():       # mixed case, e.g. "NestJS"
        return True
    if not raw[0].isupper():
        return False
    before = text[:match.start()].rstrip()
    return bool(before) and before[-1] not in _SENTENCE_END


class GrammarChecker:
    def __init__(self):
        self.spell = SpellChecker()
        self.spell.word_frequency.load_words(_EXTRA_WORDS)

    def check(self, text: str) -> dict:
        # A8: strip punctuation BEFORE the alphabetic check, skip one-letter
        # tokens (C, R), known tech vocabulary, and proper nouns, and report
        # every typo -- the old list stopped at 10, hiding problems on longer
        # resumes.
        words = set()
        for match in _WORD_RE.finditer(text or ""):
            word = match.group(0).lower()
            if len(word) < 2 or word in _KNOWN_TECH:
                continue
            if _is_proper_noun(text, match):
                continue
            words.add(word)
        typos = []
        for unknown in sorted(self.spell.unknown(words)):
            correction = self.spell.correction(unknown)
            if correction and correction != unknown:
                typos.append({"word": unknown, "suggestion": correction})

        score = max(0, 100 - (len(typos) * 5))
        return {"score": score, "typos_found": typos}
