import unittest

from app.analyzer.ats_checker import ATSCompatibilityChecker


SECTIONS = {
    "contact_parsed": {"email": "a@b.c", "phone": "1", "name": "N"},
    "_section_order": ["experience", "education", "skills"],
}


def pronoun_issues(text):
    result = ATSCompatibilityChecker().check(text, SECTIONS, {})
    return [issue for issue in result["issues"] if issue["issue"].startswith("Personal pronouns")]


class PronounWarningTests(unittest.TestCase):
    def test_pdf_pipe_contact_lines_are_ignored(self):
        text = (
            "dhanieeel0907@gmail.com I +63 967-608-6978 I Bacoor City, Cavite\n"
            "https://dl-dev-portfolio.vercel.app I https://github.com/karinaonly\n"
            "486-Hour Internship I Imus, Cavite"
        )
        self.assertEqual(pronoun_issues(text), [])

    def test_regular_resume_text_has_no_false_positive_pronouns(self):
        self.assertEqual(pronoun_issues("Built backend schemas with MySQL and PostgreSQL\nWhack-a-Mole Arduino game"), [])

    def test_real_pronouns_are_counted(self):
        issues = pronoun_issues("I built the API.\nI led the team.\nMy work improved delivery.")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["issue"], "Personal pronouns detected (3x)")
        self.assertEqual(len(issues[0]["examples"]), 3)

    def test_two_pronouns_do_not_warn(self):
        self.assertEqual(pronoun_issues("I built the API.\nMy work improved delivery."), [])


if __name__ == "__main__":
    unittest.main()