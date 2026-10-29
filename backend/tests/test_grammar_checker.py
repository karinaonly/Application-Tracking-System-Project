import unittest

from app.analyzer.grammar_checker import GrammarChecker

gc = GrammarChecker()


def words(text):
    return [t["word"] for t in gc.check(text)["typos_found"]]


class PunctuationTests(unittest.TestCase):
    """A8: punctuation must not hide a word from the spell checker."""

    def test_trailing_punctuation_is_checked(self):
        # The old `isalpha()` filter skipped "recieve," entirely.
        self.assertIn("recieve", words("We recieve system, updates."))

    def test_parenthesised_words_are_checked(self):
        self.assertIn("seperate", words("Built (seperate) reports."))

    def test_contractions_and_hyphens_are_not_typos(self):
        self.assertEqual(
            words("We don't over-engineer; it's the team's problem-solving."), []
        )

    def test_short_tokens_are_ignored(self):
        self.assertEqual(words("C, R, and Go."), [])


class TechVocabularyTests(unittest.TestCase):
    """A8: known tech terms are not typos."""

    def test_skill_names_and_acronyms_are_known(self):
        text = (
            "FastAPI, PostgreSQL, Kubernetes, GitHub, SQLModel, Node.js, "
            "CI/CD, OAuth, JWT, REST and SQL."
        )
        self.assertEqual(words(text), [])

    def test_a_real_typo_next_to_a_skill_is_still_found(self):
        self.assertEqual(words("Built APIs with kubernets and FastAPI."), ["kubernets"])

    def test_sentence_start_typo_is_still_found(self):
        self.assertEqual(words("Recieve payments from clients."), ["recieve"])

    def test_proper_nouns_and_acronyms_are_not_typos(self):
        # Company/school names, mixed-case tech names and acronyms are not
        # spelling mistakes and must not get invented corrections.
        text = (
            "Worked at Synchores with Arduino, NestJS, TypeORM, VPS and ABM "
            "while studying at Bacoor."
        )
        self.assertEqual(words(text), [])


class CoverageTests(unittest.TestCase):
    """A8: every typo is reported, not just the first ten."""

    MISSPELLINGS = [
        "recieve", "teh", "seperate", "occured", "definately", "enviroment",
        "sucessful", "managment", "responsibilty", "acheive", "wich", "thier",
    ]

    def test_more_than_ten_typos_are_all_reported(self):
        result = gc.check(" ".join(self.MISSPELLINGS))
        self.assertEqual(len(result["typos_found"]), len(self.MISSPELLINGS))
        self.assertEqual(
            sorted(t["word"] for t in result["typos_found"]),
            sorted(self.MISSPELLINGS),
        )

    def test_score_counts_every_typo(self):
        result = gc.check(" ".join(self.MISSPELLINGS))
        self.assertEqual(result["score"], max(0, 100 - len(self.MISSPELLINGS) * 5))

    def test_clean_text_scores_100(self):
        self.assertEqual(
            gc.check("Built reliable services in Python."),
            {"score": 100, "typos_found": []},
        )

    def test_empty_text_is_clean(self):
        self.assertEqual(gc.check(""), {"score": 100, "typos_found": []})


if __name__ == "__main__":
    unittest.main()
