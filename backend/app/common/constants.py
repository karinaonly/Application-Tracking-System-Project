STRONG_ACTION_VERBS = {
    "led", "directed", "managed", "oversaw", "headed", "supervised",
    "orchestrated", "spearheaded", "championed", "pioneered", "achieved",
    "exceeded", "surpassed", "delivered", "accomplished", "created",
    "designed", "developed", "built", "established", "founded", "launched",
    "initiated", "introduced", "implemented", "improved", "enhanced",
    "optimized", "streamlined", "revamped", "transformed", "modernized",
    "upgraded", "accelerated", "boosted", "analyzed", "evaluated", "assessed",
    "researched", "identified", "presented", "negotiated", "persuaded",
    "collaborated", "facilitated", "coordinated", "mentored", "trained",
    "advised", "engineered", "architected", "automated", "integrated",
    "configured", "deployed", "migrated", "refactored", "generated",
    "increased", "grew", "expanded", "drove", "captured", "secured",
    "maximized", "reduced", "saved",
    # A2: common resume verbs that used to fall through as "missing". Base
    # forms are listed so regular inflections ("maintained", "documenting")
    # resolve through is_strong_action_verb(); irregular past forms live in
    # IRREGULAR_VERB_BASES below.
    "write", "maintain", "document", "test", "debug", "troubleshoot",
    "diagnose", "resolve", "address", "support", "enable", "execute",
    "perform", "plan", "schedule", "organize", "prioritize", "allocate",
    "budget", "forecast", "track", "monitor", "measure", "report",
    "communicate", "publish", "author", "draft", "review", "edit", "audit",
    "validate", "verify", "ensure", "enforce", "standardize", "define",
    "scope", "estimate", "model", "simulate", "compute", "calculate",
    "process", "convert", "consolidate", "merge", "replace", "remove",
    "eliminate", "prevent", "mitigate", "protect", "encrypt",
    "authenticate", "authorize", "provision", "install", "patch", "update",
    "refresh", "rebuild", "restore", "scale", "tune", "profile",
    "benchmark", "host", "operate", "sustain", "repair", "fix", "onboard",
    "recruit", "coach", "teach", "guide", "own", "ship", "release",
    "raise", "earn", "lower", "decrease", "double", "triple", "cut",
    "slash", "partner", "liaise", "represent", "translate", "adapt",
    "customize", "personalize", "localize", "map", "port", "embed",
    "connect", "cache", "index", "query", "store", "sync",
    # irregular base forms used by IRREGULAR_VERB_BASES
    "lead", "build", "drive", "grow", "run", "win", "sell", "bring",
    "find", "hold", "keep", "meet", "pay", "send", "take", "think",
    "understand", "draw", "oversee", "speak", "choose", "begin", "break",
}

# A2: past-tense forms that cannot be derived by stripping "-ed"/"-ing".
IRREGULAR_VERB_BASES = {
    "wrote": "write", "written": "write", "writes": "write",
    "led": "lead", "built": "build", "drove": "drive", "driven": "drive",
    "grew": "grow", "grown": "grow", "ran": "run", "won": "win",
    "sold": "sell", "taught": "teach", "brought": "bring", "held": "hold",
    "kept": "keep", "met": "meet", "paid": "pay", "sent": "send",
    "took": "take", "taken": "take", "thought": "think",
    "understood": "understand", "drew": "draw", "drawn": "draw",
    "oversaw": "oversee", "overseen": "oversee", "spoke": "speak",
    "spoken": "speak", "chose": "choose", "chosen": "choose",
    "began": "begin", "begun": "begin", "broke": "break",
    "broken": "break",
}


def _verb_candidates(word: str) -> set[str]:
    """Possible base forms of a resume verb (cheap morphology, no spaCy)."""
    word = word.lower()
    candidates = {word}
    if word in IRREGULAR_VERB_BASES:
        candidates.add(IRREGULAR_VERB_BASES[word])
        return candidates

    def add_stem(stem: str) -> None:
        candidates.add(stem)
        candidates.add(stem + "e")
        if len(stem) > 2 and stem[-1] == stem[-2] and stem[-1] not in "aeiou":
            undoubled = stem[:-1]
            candidates.add(undoubled)
            candidates.add(undoubled + "e")

    if word.endswith("ied") and len(word) > 4:
        candidates.add(word[:-3] + "y")
    elif word.endswith("ed") and len(word) > 3:
        add_stem(word[:-2])
    elif word.endswith("ing") and len(word) > 5:
        add_stem(word[:-3])
    elif word.endswith("es") and len(word) > 4:
        candidates.add(word[:-2])
    elif word.endswith("s") and len(word) > 3:
        candidates.add(word[:-1])
    return candidates


def is_strong_action_verb(word: str) -> bool:
    """A2: recognize strong verbs in base, past, and gerund form."""
    return any(candidate in STRONG_ACTION_VERBS for candidate in _verb_candidates(word))

WEAK_VERBS = {
    "helped", "assisted", "tried", "attempted", "worked on",
    "was responsible for", "responsible for", "duties included",
    "participated in", "was involved in", "involved in", "handled",
    "dealt with", "did", "made", "got", "had", "tasked with", "in charge of"
}

WEAK_TO_STRONG = {
    "helped": ["facilitated", "enabled", "supported"],
    "assisted": ["supported", "collaborated with", "partnered with"],
    "responsible for": ["managed", "led", "oversaw", "directed"],
    "worked on": ["developed", "contributed to", "executed"],
    "handled": ["managed", "processed", "administered"],
    "dealt with": ["resolved", "addressed", "managed"],
    "participated in": ["contributed to", "collaborated on"],
    "was involved in": ["contributed to", "played a key role in"],
    "duties included": ["delivered", "executed", "performed"],
    "tasked with": ["charged with", "entrusted to"],
    "in charge of": ["directed", "managed", "oversaw"]
}

SOFT_SKILLS = {
    "communication", "leadership", "teamwork", "problem solving",
    "problem-solving", "critical thinking", "time management",
    "adaptability", "collaboration", "creativity", "attention to detail",
    "detail-oriented", "analytical", "strategic thinking", "mentoring",
    "coaching", "negotiation", "presentation", "public speaking",
    "decision making", "conflict resolution", "emotional intelligence",
    "self-motivated", "proactive", "innovative", "organizational",
    "multitasking", "interpersonal", "cross-functional", "stakeholder management"
}

SECTION_PATTERNS = {
    "contact": r"(?i)^(contact\s*(info|information|details)?|personal\s*(info|information|details)?)$",
    "summary": r"(?i)^(professional\s*summary|summary|profile|executive\s*summary|career\s*summary|about\s*me|objective|career\s*objective)$",
    "experience": r"(?i)^(work\s*experience|experience|professional\s*experience|employment\s*history|work\s*history|career\s*history|relevant\s*experience|professional\s*background)$",
    "education": r"(?i)^(education|academic\s*background|academic\s*qualifications|educational\s*background|degrees?)$",
    "skills": r"(?i)^(skills|technical\s*skills|core\s*competencies|competencies|areas?\s*of\s*expertise|proficiencies|technologies|tech\s*stack)$",
    "certifications": r"(?i)^(certifications?|licenses?\s*(&|and)?\s*certifications?|professional\s*certifications?|credentials)$",
    "projects": r"(?i)^(projects?|key\s*projects?|notable\s*projects?|personal\s*projects?)$",
    "languages": r"(?i)^(languages?|language\s*proficiency)$",
}
