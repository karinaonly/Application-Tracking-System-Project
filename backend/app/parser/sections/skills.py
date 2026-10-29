"""Skills-section parsing.

Skills arrive as comma/semicolon/slash/pipe-separated lists. Category labels
("Frontend:") are stripped, and duplicates are removed case-insensitively
while keeping the first spelling.
"""
import re

# A15: category labels inside skills lists ("Frontend: React.js, Next.js")
SKILL_CATEGORY_RE = re.compile(
    r"^(?:languages?|frontend|backend|full[- ]?stack|databases?|tools?|"
    r"frameworks?|libraries?|apis?(?:\s*&\s*orms?|\s*(?:&|and)\s*orms?)?|"
    r"devops(?:\s*&\s*tools)?|soft\s*skills|others?)\s*[:\u2013\u2014]\s*",
    re.I,
)


class SkillsParser:
    def parse(self, text: str) -> list[str]:
        if not text:
            return []
        text = re.sub(r"[•▪▸►◆○●]", ",", text)
        # A15: comma-separated skill lists are the most common format
        parts = re.split(r"[\n;/|,]", text)
        skills = []
        for p in parts:
            c = p.strip().strip("-").strip("*").strip()
            c = SKILL_CATEGORY_RE.sub("", c).strip()
            if c and 1 < len(c) < 60:
                skills.append(c)
        seen = set()
        out = []
        for s in skills:
            key = s.lower()
            if key not in seen:
                seen.add(key)
                out.append(s)
        return out
