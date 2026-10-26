import unittest
from unittest.mock import MagicMock
from uuid import uuid4

from app.common.exceptions import JobNotFoundError
from app.jobs.models import JobDescription
from app.resume.models import Resume
from app.resume.service import ResumeService


def make_resume(user_id) -> Resume:
    return Resume(
        id=uuid4(),
        user_id=user_id,
        filename="resume.pdf",
        file_path="resume.pdf",
        file_type=".pdf",
        raw_text="",
        parsed_data={"sections": {}, "metadata": {}},
    )


class AnalyzeJobOwnershipTests(unittest.TestCase):
    """A17: analyze must never use another user's job."""

    def setUp(self):
        self.service = ResumeService(MagicMock())
        self.service.ats_checker = MagicMock()
        self.service.ats_checker.check.return_value = {"score": None, "passed": [], "issues": []}
        self.service.bullet_analyzer = MagicMock()
        self.service.bullet_analyzer.analyze_bullets.return_value = {"score": None, "details": []}
        self.service.grammar = MagicMock()
        self.service.grammar.check.return_value = {"score": None}
        self.service.kw_engine = MagicMock()
        self.service.ai = MagicMock()

    def test_job_owned_by_another_user_is_rejected(self):
        owner_id = uuid4()
        other_id = uuid4()
        resume = make_resume(owner_id)
        foreign_job = JobDescription(id=uuid4(), user_id=other_id, title="X", raw_text="jd")

        def fake_get(model, _id):
            if model is Resume:
                return resume
            if model is JobDescription:
                return foreign_job
            return None

        self.service.session.get.side_effect = fake_get

        with self.assertRaises(JobNotFoundError):
            self.service.analyze(resume.id, owner_id, foreign_job.id)

        self.service.kw_engine.analyze.assert_not_called()

    def test_missing_job_is_rejected(self):
        owner_id = uuid4()
        resume = make_resume(owner_id)
        missing_job_id = uuid4()

        def fake_get(model, _id):
            if model is Resume:
                return resume
            return None

        self.service.session.get.side_effect = fake_get

        with self.assertRaises(JobNotFoundError):
            self.service.analyze(resume.id, owner_id, missing_job_id)


if __name__ == "__main__":
    unittest.main()
