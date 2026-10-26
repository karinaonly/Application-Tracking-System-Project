from sqlmodel import Session, select
from uuid import UUID
from fastapi import UploadFile, HTTPException
import os

from app.resume.models import Resume, ResumeAnalysis
from app.jobs.models import JobDescription
from app.parser.text_extractor import TextExtractor
from app.parser.section_parser import SectionParser
from app.analyzer.ats_checker import ATSCompatibilityChecker
from app.analyzer.keyword_engine import KeywordEngine
from app.analyzer.bullet_analyzer import BulletAnalyzer
from app.analyzer.grammar_checker import GrammarChecker
from app.analyzer.ai_rewriter import AIRewriter
from app.analyzer.scoring import compute_overall
from app.export.docx_exporter import DocxExporter
from app.common.exceptions import ResumeNotFoundError

# How many flagged bullets we'll attempt to send for AI rewriting per analysis.
# AIRewriter.MAX_BULLETS_PER_CALL caps what actually goes in the API request;
# this just bounds how many we try to flag in the first place.
MAX_BULLETS_TO_REWRITE = 8


class ResumeService:
    def __init__(self, session: Session):
        self.session = session
        self.extractor = TextExtractor()
        self.sec_parser = SectionParser()
        self.ats_checker = ATSCompatibilityChecker()
        self.kw_engine = KeywordEngine()
        self.bullet_analyzer = BulletAnalyzer()
        self.grammar = GrammarChecker()
        self.ai = AIRewriter()
        self.exporter = DocxExporter()

    def upload(self, file: UploadFile, user_id: UUID) -> Resume:
        if not file.filename:
            raise HTTPException(status_code=400, detail="File name is required")

        filename = file.filename
        ext = f".{filename.split('.')[-1].lower()}"
        file_bytes = file.file.read()

        extracted = self.extractor.extract(file_bytes, ext)
        parsed = self.sec_parser.parse(extracted["raw_text"])

        os.makedirs(f"./uploads/{user_id}", exist_ok=True)
        path = f"./uploads/{user_id}/{filename}"
        with open(path, "wb") as f:
            f.write(file_bytes)

        resume = Resume(
            user_id=user_id,
            filename=filename,
            file_path=path,
            file_type=ext,
            raw_text=extracted["raw_text"],
            parsed_data={"sections": parsed, "metadata": extracted["metadata"]}
        )
        self.session.add(resume)
        self.session.commit()
        self.session.refresh(resume)
        return resume

    def analyze(self, resume_id: UUID, user_id: UUID, job_id: UUID | None = None) -> ResumeAnalysis:
        resume = self.session.get(Resume, resume_id)
        if not resume or resume.user_id != user_id:
            raise ResumeNotFoundError()

        sections = resume.parsed_data.get("sections", {})
        meta = resume.parsed_data.get("metadata", {})

        ats_res = self.ats_checker.check(resume.raw_text, sections, meta)
        bullet_entries = [
            {**entry, "_section": "Experience"}
            for entry in sections.get("experience_parsed", [])
        ] + [
            {**entry, "_section": "Projects"}
            for entry in sections.get("projects_parsed", [])
        ]
        bullet_res = self.bullet_analyzer.analyze_bullets(bullet_entries)
        grammar_res = self.grammar.check(resume.raw_text)

        # No job selected => keyword score is "not available", NOT 100.
        kw_res = {
            "score": None,
            "score_available": False,
            "reason": "No job description selected.",
            "similarity": None,
            "matched_keywords": [],
            "missing_keywords": [],
        }
        target_role = ""
        if job_id:
            job = self.session.get(JobDescription, job_id)
            if job:
                target_role = job.title
                kw_res = self.kw_engine.analyze(resume.raw_text, job.raw_text)

        overall, weights_used = compute_overall({
            "ats": ats_res["score"],
            "bullets": bullet_res["score"],
            "keywords": kw_res["score"],
        })

        # AI rewrite for weak/metric-less bullets, batched into ONE API call instead of
        # one call per bullet. Truthfulness rules (no invented numbers/tools) live in AIRewriter.
        flagged = [
            b["original"] for b in bullet_res.get("details", [])
            if not b["has_metrics"] or b["verb_type"] == "weak"
        ][:MAX_BULLETS_TO_REWRITE]
        rewritten = self.ai.rewrite_bullets(
            flagged,
            target_role=target_role,
            matched_keywords=kw_res.get("matched_keywords", []),
            missing_keywords=kw_res.get("missing_keywords", []),
        ) if flagged else {}

        analysis = ResumeAnalysis(
            resume_id=resume.id,
            job_id=job_id,
            overall_score=overall,
            ats_score=ats_res["score"],
            keyword_score=kw_res["score"] or 0.0,   # 0.0 placeholder if unavailable (see report[...]["score_available"])
            bullet_score=bullet_res["score"] or 0.0,
            report={
                "overall_score": overall,
                "weights_used": weights_used,
                "ats": ats_res,
                "bullet_analysis": bullet_res,
                "keyword_analysis": kw_res,
                "grammar": grammar_res,
                "ai_rewritten_examples": rewritten
            }
        )
        self.session.add(analysis)
        self.session.commit()
        self.session.refresh(analysis)
        return analysis

    def export_docx(self, resume_id: UUID, user_id: UUID) -> bytes:
        resume = self.session.get(Resume, resume_id)
        if not resume or resume.user_id != user_id:
            raise ResumeNotFoundError()

        # Fetch latest analysis for this resume to get keywords & rewrites
        statement = select(ResumeAnalysis).where(ResumeAnalysis.resume_id == resume_id).order_by(ResumeAnalysis.created_at.desc())
        analysis = self.session.exec(statement).first()

        missing_keywords = []
        rewritten_bullets = {}
        target_role = ""

        if analysis and analysis.report:
            missing_keywords = analysis.report.get("keyword_analysis", {}).get("missing_keywords", [])
            rewritten_bullets = analysis.report.get("ai_rewritten_examples", {})

            # Fetch target job title if attached
            if analysis.job_id:
                job = self.session.get(JobDescription, analysis.job_id)
                if job:
                    target_role = job.title

        return self.exporter.export_tailored(
            sections=resume.parsed_data.get("sections", {}),
            missing_keywords=missing_keywords,
            rewritten_bullets=rewritten_bullets,
            target_role=target_role
        )
