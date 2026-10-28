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


class ImprovementScoringTests(unittest.TestCase):
    """D1: analyze() re-scores the tailored bullets and stores a before/after block."""

    def setUp(self):
        self.service = ResumeService(MagicMock())
        self.service.ats_checker = MagicMock()
        self.service.ats_checker.check.return_value = {"score": 80.0, "passed": [], "issues": []}
        self.service.grammar = MagicMock()
        self.service.grammar.check.return_value = {"score": None}
        self.service.kw_engine = MagicMock()
        self.service.kw_engine.analyze.return_value = {
            "score": 60.0, "score_available": True, "matched_keywords": ["Python"],
            "missing_keywords": ["Docker"], "reason": None,
        }
        self.service.ai = MagicMock()

    def _make_resume(self, owner_id) -> Resume:
        return Resume(
            id=uuid4(), user_id=owner_id, filename="r.pdf", file_path="r.pdf",
            file_type=".pdf",
            raw_text="Summary line here\nDid tasks for the team\nSkills: Python",
            parsed_data={"sections": {
                "experience_parsed": [{
                    "title": "Dev", "company": "Acme", "dates": "2024",
                    "bullets": ["Did tasks for the team"],
                }],
            }, "metadata": {}},
        )

    def _mock_analyzers(self, before_score, after_score):
        def analyze_side_effect(entries):
            bullets = entries[0]["bullets"]
            if bullets == ["Did tasks for the team"]:
                return {
                    "score": before_score, "score_available": True,
                    "details": [{"original": "Did tasks for the team", "has_metrics": False, "verb_type": "weak"}],
                }
            return {"score": after_score, "score_available": True, "details": []}

        analyzer = MagicMock()
        analyzer.analyze_bullets.side_effect = analyze_side_effect
        self.service.bullet_analyzer = analyzer

    def _analyze(self, resume):
        self.service.session.get.side_effect = lambda model, _id: resume if model is Resume else None
        return self.service.analyze(resume.id, resume.user_id)

    def test_improvement_block_when_rewrites_applied(self):
        owner_id = uuid4()
        resume = self._make_resume(owner_id)
        self._mock_analyzers(40.0, 85.0)
        self.service.ai.rewrite_bullets.return_value = {
            "Did tasks for the team": {
                "ai_output": "Led 5-member team", "source": "groq",
            },
        }

        analysis = self._analyze(resume)
        imp = analysis.report["improvement"]
        self.assertEqual(imp["before"]["bullets"], 40.0)
        self.assertEqual(imp["after"]["bullets"], 85.0)
        self.assertEqual(imp["applied_rewrites"], 1)
        self.assertIsNone(imp["after"]["keywords"])  # no job selected
        # after overall re-computed with the same ATS rank
        self.assertIsNotNone(imp["after"]["overall"])

    def test_no_improvement_block_when_nothing_changed(self):
        owner_id = uuid4()
        resume = self._make_resume(owner_id)
        self._mock_analyzers(40.0, 40.0)
        # Rewrite withheld: ai_output identical to original
        self.service.ai.rewrite_bullets.return_value = {
            "Did tasks for the team": {
                "ai_output": "Did tasks for the team", "source": "guard_rejected",
            },
        }

        analysis = self._analyze(resume)
        self.assertIsNone(analysis.report["improvement"])

    def test_keyword_rescore_runs_against_tailored_text(self):
        owner_id = uuid4()
        resume = self._make_resume(owner_id)
        self._mock_analyzers(40.0, 85.0)
        self.service.ai.rewrite_bullets.return_value = {
            "Did tasks for the team": {"ai_output": "Led 5-member team with Docker"},
        }

        job_id = uuid4()
        job = JobDescription(id=job_id, user_id=owner_id, title="Backend", raw_text="Python Docker")
        self.service.session.get.side_effect = lambda model, _id: (
            resume if model is Resume else job if model is JobDescription else None
        )

        def kw_side_effect(resume_text, jd_text):
            covered = "Docker" in resume_text
            return {
                "score": 100.0 if covered else 50.0, "score_available": True,
                "matched_keywords": [], "missing_keywords": [], "reason": None,
            }

        self.service.kw_engine.analyze.side_effect = kw_side_effect

        analysis = self.service.analyze(resume.id, owner_id, job_id)
        imp = analysis.report["improvement"]
        # raw_text has no "Docker"; the tailored replacement does — after keywords re-scored
        self.assertEqual(imp["before"]["keywords"], 50.0)
        self.assertEqual(imp["after"]["keywords"], 100.0)


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
