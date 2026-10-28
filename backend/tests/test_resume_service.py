import unittest
from unittest.mock import MagicMock
from uuid import uuid4

from app.common.exceptions import AnalysisNotFoundError, JobNotFoundError
from app.jobs.models import JobDescription
from app.resume.models import Resume, ResumeAnalysis
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


def make_analysis(resume_id, report=None) -> ResumeAnalysis:
    return ResumeAnalysis(
        id=uuid4(),
        resume_id=resume_id,
        overall_score=70.0,
        ats_score=80.0,
        keyword_score=60.0,
        bullet_score=50.0,
        report=report or {},
    )


class ExportAnalysisSelectionTests(unittest.TestCase):
    """A18: export must use the analysis the user is viewing, not blindly 'the latest'."""

    def setUp(self):
        self.service = ResumeService(MagicMock())
        self.exporter = MagicMock()
        self.exporter.export_tailored.return_value = b"docx"
        self.service.exporter = self.exporter

    def test_requested_analysis_rewrites_are_used(self):
        owner_id = uuid4()
        resume = make_resume(owner_id)
        selected = make_analysis(resume.id, {"ai_rewritten_examples": {"b": {"ai_output": "SELECTED"}}})
        other = make_analysis(resume.id, {"ai_rewritten_examples": {"b": {"ai_output": "LATEST"}}})

        def fake_get(model, _id):
            if model is Resume:
                return resume
            if model is ResumeAnalysis and _id == selected.id:
                return selected
            return None

        self.service.session.get.side_effect = fake_get

        self.service.export_docx(resume.id, owner_id, selected.id)

        kwargs = self.exporter.export_tailored.call_args.kwargs
        self.assertEqual(kwargs["rewritten_bullets"], {"b": {"ai_output": "SELECTED"}})

    def test_analysis_from_another_resume_is_rejected(self):
        owner_id = uuid4()
        resume = make_resume(owner_id)
        foreign = make_analysis(uuid4(), {})

        def fake_get(model, _id):
            if model is Resume:
                return resume
            if model is ResumeAnalysis and _id == foreign.id:
                return foreign
            return None

        self.service.session.get.side_effect = fake_get

        with self.assertRaises(AnalysisNotFoundError):
            self.service.export_docx(resume.id, owner_id, foreign.id)

    def test_falls_back_to_latest_without_analysis_id(self):
        owner_id = uuid4()
        resume = make_resume(owner_id)
        latest = make_analysis(resume.id, {"ai_rewritten_examples": {"b": {"ai_output": "LATEST"}}})

        self.service.session.get.side_effect = lambda model, _id: resume if model is Resume else None
        fake_result = MagicMock()
        fake_result.first.return_value = latest
        self.service.session.exec.return_value = fake_result

        self.service.export_docx(resume.id, owner_id)

        kwargs = self.exporter.export_tailored.call_args.kwargs
        self.assertEqual(kwargs["rewritten_bullets"], {"b": {"ai_output": "LATEST"}})


if __name__ == "__main__":
    unittest.main()
