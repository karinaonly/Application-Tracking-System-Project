import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException
from sqlmodel import SQLModel, Session, create_engine

from app.analyzer.ai_rewriter import AIRewriter
from app.auth.models import User  # registers the users table for real-DB tests
from app.common.exceptions import AnalysisNotFoundError, JobNotFoundError, ResumeNotFoundError, VersionNotFoundError
from app.jobs.models import JobDescription
from app.resume.models import Resume, ResumeAnalysis, ResumeVersion
from app.resume.service import ResumeService, clear_shared_components


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


def make_analysis(resume_id, report=None, job_id=None) -> ResumeAnalysis:
    return ResumeAnalysis(
        id=uuid4(),
        resume_id=resume_id,
        job_id=job_id,
        overall_score=70.0,
        ats_score=80.0,
        keyword_score=60.0,
        bullet_score=50.0,
        report=report or {},
    )


class SharedAnalyzerTests(unittest.TestCase):
    """C5/F6: analyzers and the AI client are created once per process."""

    def tearDown(self):
        clear_shared_components()

    def test_services_share_the_same_analyzer_instances(self):
        first = ResumeService(MagicMock())
        second = ResumeService(MagicMock())

        self.assertIs(first.ai, second.ai)
        self.assertIs(first.grammar, second.grammar)
        self.assertIs(first.kw_engine, second.kw_engine)
        self.assertIs(first.ats_checker, second.ats_checker)
        self.assertIs(first.exporter, second.exporter)

    def test_ai_rewriter_is_constructed_once(self):
        clear_shared_components()
        with patch("app.resume.service.AIRewriter", wraps=AIRewriter) as ctor:
            ResumeService(MagicMock())
            ResumeService(MagicMock())
        self.assertEqual(ctor.call_count, 1)

    def test_clear_rebuilds_the_shared_set(self):
        first = ResumeService(MagicMock())
        clear_shared_components()
        second = ResumeService(MagicMock())

        self.assertIsNot(first.ai, second.ai)
        self.assertIsNot(first.grammar, second.grammar)


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

        def kw_side_effect(resume_text, jd_text, **_kwargs):
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

    def test_job_skill_buckets_are_forwarded_to_keyword_engine(self):
        """B8: D2's required/preferred buckets must reach the keyword engine."""
        owner_id = uuid4()
        resume = self._make_resume(owner_id)
        self._mock_analyzers(40.0, 85.0)
        self.service.ai.rewrite_bullets.return_value = {}

        job_id = uuid4()
        job = JobDescription(
            id=job_id, user_id=owner_id, title="Backend", raw_text="Python Docker",
            extracted_keywords={
                "required_skills": ["Docker"],
                "preferred_skills": ["Python"],
                "other_skills": [],
            },
        )
        self.service.session.get.side_effect = lambda model, _id: (
            resume if model is Resume else job if model is JobDescription else None
        )

        self.service.analyze(resume.id, owner_id, job_id)

        _, kwargs = self.service.kw_engine.analyze.call_args
        self.assertEqual(kwargs["required_skills"], ["Docker"])
        self.assertEqual(kwargs["preferred_skills"], ["Python"])


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
        # C6: an accepted rewrite is what reaches the exporter.
        selected = make_analysis(resume.id, {
            "ai_rewritten_examples": {"b": {"ai_output": "SELECTED"}},
            "rewrite_decisions": {"b": {"action": "accepted", "text": "SELECTED"}},
        })
        other = make_analysis(resume.id, {
            "ai_rewritten_examples": {"b": {"ai_output": "LATEST"}},
            "rewrite_decisions": {"b": {"action": "accepted", "text": "LATEST"}},
        })

        def fake_get(model, _id):
            if model is Resume:
                return resume
            if model is ResumeAnalysis and _id == selected.id:
                return selected
            return None

        self.service.session.get.side_effect = fake_get

        self.service.export_docx(resume.id, owner_id, selected.id)

        kwargs = self.exporter.export_tailored.call_args.kwargs
        self.assertEqual(kwargs["rewritten_bullets"], {"b": "SELECTED"})

    def test_unreviewed_rewrites_are_not_applied(self):
        # C6: a fresh analysis has suggestions but no decisions — exporting it
        # must keep the original bullets, not silently apply the AI text.
        owner_id = uuid4()
        resume = make_resume(owner_id)
        analysis = make_analysis(resume.id, {
            "ai_rewritten_examples": {"b": {"ai_output": "AI TEXT"}},
        })

        def fake_get(model, _id):
            if model is Resume:
                return resume
            if model is ResumeAnalysis and _id == analysis.id:
                return analysis
            return None

        self.service.session.get.side_effect = fake_get

        self.service.export_docx(resume.id, owner_id, analysis.id)

        kwargs = self.exporter.export_tailored.call_args.kwargs
        self.assertEqual(kwargs["rewritten_bullets"], {})

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
        latest = make_analysis(resume.id, {
            "ai_rewritten_examples": {"b": {"ai_output": "LATEST"}},
            "rewrite_decisions": {"b": {"action": "accepted", "text": "LATEST"}},
        })

        self.service.session.get.side_effect = lambda model, _id: resume if model is Resume else None
        fake_result = MagicMock()
        fake_result.first.return_value = latest
        self.service.session.exec.return_value = fake_result

        self.service.export_docx(resume.id, owner_id)

        kwargs = self.exporter.export_tailored.call_args.kwargs
        self.assertEqual(kwargs["rewritten_bullets"], {"b": "LATEST"})

    def test_export_passes_only_confirmed_keywords(self):
        # A3: raw missing keywords never reach the exporter — only the
        # subset the user confirmed they actually have.
        owner_id = uuid4()
        resume = make_resume(owner_id)
        analysis = make_analysis(resume.id, report={
            "keyword_analysis": {"missing_keywords": ["Docker", "Kubernetes", "Terraform"]},
            "confirmed_keywords": ["Docker"],
        })

        self.service.session.get.side_effect = lambda model, _id: resume if model is Resume else None
        fake_result = MagicMock()
        fake_result.first.return_value = analysis
        self.service.session.exec.return_value = fake_result

        self.service.export_docx(resume.id, owner_id)

        kwargs = self.exporter.export_tailored.call_args.kwargs
        self.assertEqual(kwargs["missing_keywords"], ["Docker"])

    def test_export_without_confirmation_passes_no_keywords(self):
        # A3: an analysis with no confirmed keywords exports no additional
        # skills — the pre-A3 behavior silently ignored them anyway.
        owner_id = uuid4()
        resume = make_resume(owner_id)
        analysis = make_analysis(resume.id, report={
            "keyword_analysis": {"missing_keywords": ["Docker"]},
        })

        self.service.session.get.side_effect = lambda model, _id: resume if model is Resume else None
        fake_result = MagicMock()
        fake_result.first.return_value = analysis
        self.service.session.exec.return_value = fake_result

        self.service.export_docx(resume.id, owner_id)

        kwargs = self.exporter.export_tailored.call_args.kwargs
        self.assertEqual(kwargs["missing_keywords"], [])


class ConfirmKeywordsTests(unittest.TestCase):
    """A3: the user confirms which missing keywords they actually have."""

    def setUp(self):
        self.service = ResumeService(MagicMock())

    def _wire(self, resume, analysis):
        def fake_get(model, _id):
            if model is Resume:
                return resume
            if model is ResumeAnalysis:
                return analysis
            return None

        self.service.session.get.side_effect = fake_get

    def test_confirmed_keywords_stored_with_canonical_spelling(self):
        owner_id = uuid4()
        resume = make_resume(owner_id)
        analysis = make_analysis(resume.id, report={
            "keyword_analysis": {"missing_keywords": ["PostgreSQL", "docker compose", "Terraform"]},
        })
        self._wire(resume, analysis)

        confirmed, soft_skipped = self.service.confirm_keywords(
            resume.id, analysis.id, owner_id, ["postgresql", "Docker Compose"]
        )

        # canonical spellings from the analysis's own missing list
        self.assertEqual(confirmed, ["PostgreSQL", "docker compose"])
        self.assertEqual(soft_skipped, [])
        self.assertEqual(analysis.report["confirmed_keywords"], confirmed)
        self.service.session.add.assert_called()
        self.service.session.commit.assert_called()

    def test_keyword_outside_missing_list_is_rejected(self):
        owner_id = uuid4()
        resume = make_resume(owner_id)
        analysis = make_analysis(resume.id, report={
            "keyword_analysis": {"missing_keywords": ["Docker"]},
        })
        self._wire(resume, analysis)

        with self.assertRaises(HTTPException) as ctx:
            self.service.confirm_keywords(resume.id, analysis.id, owner_id, ["Kubernetes"])
        self.assertEqual(ctx.exception.status_code, 400)
        # nothing stored when the request is rejected
        self.assertNotIn("confirmed_keywords", analysis.report)
        self.service.session.commit.assert_not_called()

    def test_empty_selection_is_rejected(self):
        owner_id = uuid4()
        resume = make_resume(owner_id)
        analysis = make_analysis(resume.id, report={
            "keyword_analysis": {"missing_keywords": ["Docker"]},
        })
        self._wire(resume, analysis)

        with self.assertRaises(HTTPException) as ctx:
            self.service.confirm_keywords(resume.id, analysis.id, owner_id, [])
        self.assertEqual(ctx.exception.status_code, 400)

    def test_soft_skills_are_skipped_not_stored(self):
        owner_id = uuid4()
        resume = make_resume(owner_id)
        analysis = make_analysis(resume.id, report={
            "keyword_analysis": {"missing_keywords": ["Communication", "Docker"]},
        })
        self._wire(resume, analysis)

        confirmed, soft_skipped = self.service.confirm_keywords(
            resume.id, analysis.id, owner_id, ["Communication", "Docker"]
        )

        self.assertEqual(confirmed, ["Docker"])
        self.assertEqual(soft_skipped, ["Communication"])
        self.assertEqual(analysis.report["confirmed_keywords"], ["Docker"])

    def test_only_soft_skills_is_rejected(self):
        owner_id = uuid4()
        resume = make_resume(owner_id)
        analysis = make_analysis(resume.id, report={
            "keyword_analysis": {"missing_keywords": ["Communication"]},
        })
        self._wire(resume, analysis)

        with self.assertRaises(HTTPException) as ctx:
            self.service.confirm_keywords(
                resume.id, analysis.id, owner_id, ["Communication"]
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertNotIn("confirmed_keywords", analysis.report)

    def test_foreign_analysis_is_rejected(self):
        owner_id = uuid4()
        resume = make_resume(owner_id)
        foreign = make_analysis(uuid4(), report={
            "keyword_analysis": {"missing_keywords": ["Docker"]},
        })
        self._wire(resume, foreign)

        with self.assertRaises(AnalysisNotFoundError):
            self.service.confirm_keywords(resume.id, foreign.id, owner_id, ["Docker"])

    def test_foreign_resume_is_rejected(self):
        owner_id = uuid4()
        resume = make_resume(owner_id)
        analysis = make_analysis(resume.id, report={
            "keyword_analysis": {"missing_keywords": ["Docker"]},
        })

        def fake_get(model, _id):
            if model is Resume:
                return make_resume(uuid4())  # someone else's resume
            return None

        self.service.session.get.side_effect = fake_get

        with self.assertRaises(ResumeNotFoundError):
            self.service.confirm_keywords(resume.id, analysis.id, owner_id, ["Docker"])


class ConfirmRewriteTests(unittest.TestCase):
    """C6: AI rewrites reach the export only after the user reviews them."""

    ORIGINAL = "Did tasks for the team"

    def setUp(self):
        self.service = ResumeService(MagicMock())

    def _wire(self, resume, analysis):
        def fake_get(model, _id):
            if model is Resume:
                return resume
            if model is ResumeAnalysis:
                return analysis
            return None

        self.service.session.get.side_effect = fake_get

    def _analysis(self, resume, **extra):
        report = {
            "ai_rewritten_examples": {
                self.ORIGINAL: {
                    "ai_output": "Led a 5-person team to deliver the release",
                    "moderate": "Led a 5-person team to deliver the release",
                    "aggressive": "Directed a 5-person team to ship the release on time",
                    "source": "groq",
                },
            },
        }
        report.update(extra)
        return make_analysis(resume.id, report=report)

    def test_accept_applies_moderate_rewrite(self):
        owner_id = uuid4()
        resume = make_resume(owner_id)
        analysis = self._analysis(resume)
        self._wire(resume, analysis)

        stored, applied = self.service.confirm_rewrites(
            resume.id, analysis.id, owner_id,
            [{"original": self.ORIGINAL, "action": "accepted"}],
        )

        self.assertEqual(stored[self.ORIGINAL]["action"], "accepted")
        self.assertEqual(
            stored[self.ORIGINAL]["text"],
            "Led a 5-person team to deliver the release",
        )
        self.assertEqual(applied, 1)
        self.assertEqual(analysis.report["rewrite_decisions"], stored)
        self.service.session.commit.assert_called()

    def test_accept_with_edit_uses_edited_text(self):
        owner_id = uuid4()
        resume = make_resume(owner_id)
        analysis = self._analysis(resume)
        self._wire(resume, analysis)

        stored, applied = self.service.confirm_rewrites(
            resume.id, analysis.id, owner_id,
            [{
                "original": self.ORIGINAL,
                "action": "accepted",
                "text": "  Led a 4-person team to deliver the release  ",
            }],
        )

        self.assertEqual(
            stored[self.ORIGINAL]["text"], "Led a 4-person team to deliver the release"
        )
        self.assertEqual(applied, 1)

    def test_reject_keeps_original_bullet(self):
        owner_id = uuid4()
        resume = make_resume(owner_id)
        analysis = self._analysis(resume)
        self._wire(resume, analysis)

        stored, applied = self.service.confirm_rewrites(
            resume.id, analysis.id, owner_id,
            [{"original": self.ORIGINAL, "action": "rejected"}],
        )

        self.assertEqual(stored[self.ORIGINAL], {"action": "rejected", "text": ""})
        self.assertEqual(applied, 0)

    def test_placeholder_cannot_be_accepted(self):
        owner_id = uuid4()
        resume = make_resume(owner_id)
        analysis = self._analysis(resume)
        self._wire(resume, analysis)

        with self.assertRaises(HTTPException) as ctx:
            self.service.confirm_rewrites(
                resume.id, analysis.id, owner_id,
                [{
                    "original": self.ORIGINAL,
                    "action": "accepted",
                    "text": "Led a [X]-person team to deliver the release",
                }],
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("[X]", ctx.exception.detail)
        self.assertNotIn("rewrite_decisions", analysis.report)
        self.service.session.commit.assert_not_called()

    def test_unknown_original_is_rejected(self):
        owner_id = uuid4()
        resume = make_resume(owner_id)
        analysis = self._analysis(resume)
        self._wire(resume, analysis)

        with self.assertRaises(HTTPException) as ctx:
            self.service.confirm_rewrites(
                resume.id, analysis.id, owner_id,
                [{"original": "A bullet that was never rewritten", "action": "accepted"}],
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertNotIn("rewrite_decisions", analysis.report)

    def test_decisions_merge_one_card_at_a_time(self):
        owner_id = uuid4()
        resume = make_resume(owner_id)
        second = "Managed the backlog"
        analysis = make_analysis(resume.id, report={
            "ai_rewritten_examples": {
                self.ORIGINAL: {"ai_output": "Led a team"},
                second: {"ai_output": "Prioritized the backlog"},
            },
        })
        self._wire(resume, analysis)

        self.service.confirm_rewrites(
            resume.id, analysis.id, owner_id,
            [{"original": self.ORIGINAL, "action": "accepted"}],
        )
        stored, applied = self.service.confirm_rewrites(
            resume.id, analysis.id, owner_id,
            [{"original": second, "action": "accepted"}],
        )

        self.assertEqual(set(stored), {self.ORIGINAL, second})
        self.assertEqual(applied, 2)

    def test_pending_clears_a_previous_decision(self):
        owner_id = uuid4()
        resume = make_resume(owner_id)
        analysis = self._analysis(resume, rewrite_decisions={
            self.ORIGINAL: {"action": "accepted", "text": "Led a team"},
        })
        self._wire(resume, analysis)

        stored, applied = self.service.confirm_rewrites(
            resume.id, analysis.id, owner_id,
            [{"original": self.ORIGINAL, "action": "pending"}],
        )

        self.assertEqual(stored, {})
        self.assertEqual(applied, 0)
        self.assertEqual(analysis.report["rewrite_decisions"], {})

    def test_empty_decisions_are_rejected(self):
        owner_id = uuid4()
        resume = make_resume(owner_id)
        analysis = self._analysis(resume)
        self._wire(resume, analysis)

        with self.assertRaises(HTTPException) as ctx:
            self.service.confirm_rewrites(resume.id, analysis.id, owner_id, [])
        self.assertEqual(ctx.exception.status_code, 400)

    def test_foreign_analysis_is_rejected(self):
        owner_id = uuid4()
        resume = make_resume(owner_id)
        foreign = make_analysis(uuid4(), report={
            "ai_rewritten_examples": {self.ORIGINAL: {"ai_output": "Led a team"}},
        })
        self._wire(resume, foreign)

        with self.assertRaises(AnalysisNotFoundError):
            self.service.confirm_rewrites(
                resume.id, foreign.id, owner_id,
                [{"original": self.ORIGINAL, "action": "accepted"}],
            )

    def test_foreign_resume_is_rejected(self):
        owner_id = uuid4()
        resume = make_resume(owner_id)
        analysis = self._analysis(resume)

        def fake_get(model, _id):
            if model is Resume:
                return make_resume(uuid4())  # someone else's resume
            return None

        self.service.session.get.side_effect = fake_get

        with self.assertRaises(ResumeNotFoundError):
            self.service.confirm_rewrites(
                resume.id, analysis.id, owner_id,
                [{"original": self.ORIGINAL, "action": "accepted"}],
            )


class VersionTests(unittest.TestCase):
    """D3: per-job tailored resume versions stored server-side."""

    def setUp(self):
        self.service = ResumeService(MagicMock())
        self.exporter = MagicMock()
        self.exporter.export_tailored.return_value = b"docx"
        self.service.exporter = self.exporter

    def _make_resume(self, owner_id) -> Resume:
        return Resume(
            id=uuid4(), user_id=owner_id, filename="r.pdf", file_path="r.pdf",
            file_type=".pdf",
            raw_text="Summary line here\nDid tasks for the team\nSkills: Python",
            parsed_data={"sections": {
                "experience": {"raw": "Did tasks for the team"},
                "experience_parsed": [{
                    "title": "Dev", "company": "Acme", "dates": "2024",
                    "bullets": ["Did tasks for the team"],
                }],
            }, "metadata": {}},
        )

    def _make_analysis(self, resume, job_id=None, ai_output="Led 5-member team") -> ResumeAnalysis:
        # C6: a rewrite only reaches a version once the user accepts it.
        return make_analysis(resume.id, report={
            "ai_rewritten_examples": {
                "Did tasks for the team": {"ai_output": ai_output, "source": "groq"},
            },
            "rewrite_decisions": {
                "Did tasks for the team": {"action": "accepted", "text": ai_output},
            },
        }, job_id=job_id)

    def _wire_session(self, resume, analysis, job=None, existing_version=None):
        def fake_get(model, _id):
            if model is Resume:
                return resume
            if model is ResumeAnalysis:
                return analysis
            if model is JobDescription:
                return job
            if model is ResumeVersion:
                return existing_version
            return None

        self.service.session.get.side_effect = fake_get
        fake_result = MagicMock()
        fake_result.first.return_value = existing_version
        self.service.session.exec.return_value = fake_result

    def test_version_stores_tailored_text_and_sections(self):
        owner_id = uuid4()
        resume = self._make_resume(owner_id)
        job = JobDescription(id=uuid4(), user_id=owner_id, title="Backend", raw_text="jd")
        analysis = self._make_analysis(resume, job_id=job.id)
        self._wire_session(resume, analysis, job=job)

        version = self.service.create_version(resume.id, owner_id, analysis.id)

        self.assertEqual(version.job_id, job.id)
        self.assertEqual(version.label, "Tailored for Backend")
        self.assertEqual(version.applied_rewrites, {"Did tasks for the team": "Led 5-member team"})
        # raw text and both section shapes carry the rewrite
        self.assertIn("Led 5-member team", version.raw_text)
        self.assertNotIn("Did tasks for the team", version.raw_text)
        self.assertEqual(
            version.parsed_data["sections"]["experience_parsed"][0]["bullets"],
            ["Led 5-member team"],
        )
        self.assertEqual(version.parsed_data["sections"]["experience"]["raw"], "Led 5-member team")

    def test_version_with_no_applied_rewrites_is_rejected(self):
        owner_id = uuid4()
        resume = self._make_resume(owner_id)
        # rewrite withheld: ai_output identical to the original
        analysis = self._make_analysis(resume, ai_output="Did tasks for the team")
        self._wire_session(resume, analysis)

        with self.assertRaises(HTTPException) as ctx:
            self.service.create_version(resume.id, owner_id, analysis.id)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_version_from_foreign_analysis_is_rejected(self):
        owner_id = uuid4()
        resume = self._make_resume(owner_id)
        analysis = self._make_analysis(resume)
        analysis.resume_id = uuid4()  # belongs to a different resume
        self._wire_session(resume, analysis)

        with self.assertRaises(AnalysisNotFoundError):
            self.service.create_version(resume.id, owner_id, analysis.id)

    def test_version_for_foreign_resume_is_rejected(self):
        owner_id = uuid4()
        resume = self._make_resume(owner_id)
        analysis = self._make_analysis(resume)

        def fake_get(model, _id):
            return resume if model is Resume else None

        self.service.session.get.side_effect = fake_get

        with self.assertRaises(ResumeNotFoundError):
            self.service.create_version(resume.id, uuid4(), analysis.id)

    def test_version_upsert_replaces_previous_for_same_job(self):
        owner_id = uuid4()
        resume = self._make_resume(owner_id)
        job = JobDescription(id=uuid4(), user_id=owner_id, title="Backend", raw_text="jd")
        analysis = self._make_analysis(resume, job_id=job.id)
        previous = ResumeVersion(
            id=uuid4(), resume_id=resume.id, job_id=job.id, analysis_id=uuid4(),
            label="Tailored for Backend", raw_text="old", parsed_data={},
            applied_rewrites={"old": "older"},
        )
        self._wire_session(resume, analysis, job=job, existing_version=previous)

        version = self.service.create_version(resume.id, owner_id, analysis.id)

        self.assertIs(version, previous)  # updated in place, not duplicated
        self.assertEqual(version.analysis_id, analysis.id)
        self.assertEqual(version.raw_text, resume.raw_text.replace("Did tasks for the team", "Led 5-member team"))
        self.assertEqual(version.applied_rewrites, {"Did tasks for the team": "Led 5-member team"})

    def test_export_version_uses_stored_sections_and_job_title(self):
        owner_id = uuid4()
        resume = self._make_resume(owner_id)
        job = JobDescription(id=uuid4(), user_id=owner_id, title="Backend Dev", raw_text="jd")
        analysis = make_analysis(resume.id, report={
            # A3: raw missing keywords must NOT reach the export — only the
            # user-confirmed subset does.
            "keyword_analysis": {"missing_keywords": ["Docker", "Kubernetes"]},
            "confirmed_keywords": ["Docker"],
        })
        version = ResumeVersion(
            id=uuid4(), resume_id=resume.id, job_id=job.id, analysis_id=analysis.id,
            label="Tailored for Backend Dev",
            raw_text="tailored",
            parsed_data={"sections": {"experience_parsed": [{"bullets": ["Led 5-member team"]}]}},
            applied_rewrites={"Did tasks for the team": "Led 5-member team"},
        )
        self._wire_session(resume, analysis, job=job, existing_version=version)

        data, filename = self.service.export_version_docx(resume.id, version.id, owner_id)

        self.assertEqual(data, b"docx")
        # A4: the job title is passed through but NOT applied by default, so
        # the filename must not claim the job either.
        self.assertEqual(filename, "ATS_Optimized_Resume.docx")
        kwargs = self.exporter.export_tailored.call_args.kwargs
        # bullets are already tailored in the stored sections -- no rewrite map passed
        self.assertEqual(kwargs["rewritten_bullets"], {})
        self.assertEqual(kwargs["sections"], version.parsed_data["sections"])
        self.assertEqual(kwargs["target_role"], "Backend Dev")
        self.assertFalse(kwargs["match_title"])
        self.assertEqual(kwargs["missing_keywords"], ["Docker"])

    def test_export_version_can_match_the_job_title_on_request(self):
        owner_id = uuid4()
        resume = self._make_resume(owner_id)
        job = JobDescription(id=uuid4(), user_id=owner_id, title="Backend Dev", raw_text="jd")
        analysis = make_analysis(resume.id, report={})
        version = ResumeVersion(
            id=uuid4(), resume_id=resume.id, job_id=job.id, analysis_id=analysis.id,
            label="Tailored for Backend Dev", raw_text="tailored",
            parsed_data={"sections": {}}, applied_rewrites={},
        )
        self._wire_session(resume, analysis, job=job, existing_version=version)

        _, filename = self.service.export_version_docx(
            resume.id, version.id, owner_id, match_title=True
        )

        self.assertEqual(filename, "Resume_Tailored_Backend_Dev.docx")
        kwargs = self.exporter.export_tailored.call_args.kwargs
        self.assertTrue(kwargs["match_title"])

    def test_export_foreign_version_is_rejected(self):
        owner_id = uuid4()
        resume = self._make_resume(owner_id)
        version = ResumeVersion(
            id=uuid4(), resume_id=uuid4(), job_id=None, analysis_id=uuid4(),
            label="x", raw_text="", parsed_data={}, applied_rewrites={},
        )
        self._wire_session(resume, None)

        with self.assertRaises(VersionNotFoundError):
            self.service.export_version_docx(resume.id, version.id, owner_id)


class ConfirmKeywordsPersistenceTests(unittest.TestCase):
    """A3 regression: the JSON column update must survive a new session.

    Mocks could not catch this — the service mutated the report dict in place
    and reassigned the same object, so SQLAlchemy emitted no UPDATE. The API
    returned 200 and the UI showed confirmed chips, but exports read `None`.
    This test uses a real SQLite DB and a fresh session for the export.
    """

    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
        )
        SQLModel.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.service = ResumeService(self.session)
        self.owner_id = uuid4()
        self.resume = make_resume(self.owner_id)
        self.analysis = make_analysis(self.resume.id, report={
            "keyword_analysis": {"missing_keywords": ["SQL", "Linux"]},
        })
        self.session.add(self.resume)
        self.session.add(self.analysis)
        self.session.commit()

    def tearDown(self):
        self.session.close()

    def test_confirmation_is_visible_to_a_fresh_session_and_export(self):
        self.service.confirm_keywords(
            self.resume.id, self.analysis.id, self.owner_id, ["SQL", "Linux"]
        )

        with Session(self.engine) as fresh:
            stored = fresh.get(ResumeAnalysis, self.analysis.id)
            self.assertEqual(
                stored.report["confirmed_keywords"], ["SQL", "Linux"]
            )
            # the export request opens its own session — it must see them
            svc = ResumeService(fresh)
            exporter = MagicMock()
            exporter.export_tailored.return_value = b"docx"
            svc.exporter = exporter
            svc.export_docx(self.resume.id, self.owner_id, self.analysis.id)
            kwargs = exporter.export_tailored.call_args.kwargs
            self.assertEqual(kwargs["missing_keywords"], ["SQL", "Linux"])


if __name__ == "__main__":
    unittest.main()
