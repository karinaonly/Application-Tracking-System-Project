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
    "maximized", "reduced", "saved"
}

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
