from spellchecker import SpellChecker

class GrammarChecker:
    def __init__(self):
        self.spell = SpellChecker()
        self.spell.word_frequency.load_words([
            "fastapi", "docker", "kubernetes", "sqlmodel", "aws", "gcp",
            "frontend", "backend", "fullstack", "github", "linkedin", "devops",
            "microservices", "cicd", "restful", "oauth", "jwt", "nosql"
        ])

    def check(self, text: str) -> dict:
        words = [w.strip(".,;:()[]\"'").lower() for w in text.split() if w.isalpha()]
        unknown = self.spell.unknown(words)
        typos = []
        for u in list(unknown)[:10]:
            corr = self.spell.correction(u)
            if corr and corr != u:
                typos.append({"word": u, "suggestion": corr})

        score = max(0, 100 - (len(typos) * 5))
        return {"score": score, "typos_found": typos}
