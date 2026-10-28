from sqlmodel import Session, select
from uuid import UUID
from datetime import datetime, timezone
from fastapi import UploadFile, HTTPException
import os
import re

from app.resume.models import Resume, ResumeAnalysis, ResumeVersion
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
from app.common.exceptions import AnalysisNotFoundError, JobNotFoundError, ResumeNotFoundError, VersionNotFoundError
from app.common.skills import is_soft_skill

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
        job_obj = None
        if job_id:
            # A17: never analyze against another user's job (or a nonexistent one)
            job_obj = self.session.get(JobDescription, job_id)
            if not job_obj or job_obj.user_id != user_id:
                raise JobNotFoundError()
            target_role = job_obj.title
            kw_res = self.kw_engine.analyze(resume.raw_text, job_obj.raw_text)

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

        # D1: before/after re-scoring — re-run the analyzers on the tailored
        # text (only rewrites that actually changed a bullet) so the report can
        # show the projected improvement honestly.
        improvement = self._score_improvement(
            resume, bullet_entries, bullet_res, kw_res, ats_res, overall, rewritten, job_obj
        )

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
                "ai_rewritten_examples": rewritten,
                "improvement": improvement,
            }
        )
        self.session.add(analysis)
        self.session.commit()
        self.session.refresh(analysis)
        return analysis

    @staticmethod
    def _replace_bullet_text(text: str, original: str, replacement: str) -> str:
        """Replace `original` in raw text, tolerating PDF line wraps (the parsed
        bullet is 'React.js, NestJS, and MySQL' while raw_text stores
        'React.js, NestJS,\\nand MySQL'). Returns text unchanged if not found."""
        pattern = r"\s+".join(re.escape(w) for w in original.split())
        return re.sub(pattern, lambda _m: replacement, text, count=1)

    def _score_improvement(
        self,
        resume: Resume,
        bullet_entries: list,
        before_bullets: dict,
        before_keywords: dict,
        ats_res: dict,
        before_overall: float,
        rewritten: dict,
        job_obj: JobDescription | None,
    ) -> dict | None:
        # Only rewrites that actually changed a bullet contribute — withheld or
        # fallback rewrites are already identical to the original.
        applied = {
            orig: opt for orig, opt in rewritten.items()
            if isinstance(opt, dict)
            and opt.get("ai_output")
            and opt["ai_output"].strip() != orig.strip()
        }
        if not applied:
            return None

        # Same population as the before-pass (ALL experience/projects entries),
        # with only the rewritten bullets substituted — otherwise the two
        # scores are computed over different bullet sets and lie.
        tailored_entries = [
            {
                **entry,
                "bullets": [
                    applied[b]["ai_output"] if b in applied else b
                    for b in entry.get("bullets", [])
                ],
            }
            for entry in bullet_entries
        ]
        after_bullets = self.bullet_analyzer.analyze_bullets(tailored_entries)

        after_keywords: dict | None = None
        if job_obj and before_keywords.get("score") is not None:
            tailored_text = resume.raw_text
            for orig, opt in applied.items():
                tailored_text = self._replace_bullet_text(tailored_text, orig, opt["ai_output"])
            after_keywords = self.kw_engine.analyze(tailored_text, job_obj.raw_text)

        # ATS compatibility is format-based: bullet rewrites don't change it, so
        # it carries over unchanged rather than being faked as improved.
        after_overall, _ = compute_overall({
            "ats": ats_res["score"],
            "bullets": after_bullets.get("score"),
            "keywords": (after_keywords or {}).get("score"),
        })

        return {
            "applied_rewrites": len(applied),
            "flagged_bullets": len(rewritten),
            "before": {
                "overall": before_overall,
                "bullets": before_bullets.get("score"),
                "keywords": before_keywords.get("score"),
            },
            "after": {
                "overall": after_overall,
                "bullets": after_bullets.get("score"),
                "keywords": (after_keywords or {}).get("score"),
            },
        }

    def export_docx(
        self,
        resume_id: UUID,
        user_id: UUID,
        analysis_id: UUID | None = None,
        match_title: bool = False,
    ) -> bytes:
        resume = self.session.get(Resume, resume_id)
        if not resume or resume.user_id != user_id:
            raise ResumeNotFoundError()

        # A18: export the analysis the user is viewing, not blindly "the
        # latest" — viewing analysis A and exporting could otherwise produce
        # analysis B's keywords/rewrites.
        if analysis_id:
            analysis = self.session.get(ResumeAnalysis, analysis_id)
            if not analysis or analysis.resume_id != resume_id:
                raise AnalysisNotFoundError()
        else:
            statement = select(ResumeAnalysis).where(ResumeAnalysis.resume_id == resume_id).order_by(ResumeAnalysis.created_at.desc())
            analysis = self.session.exec(statement).first()

        confirmed_keywords = []
        rewritten_bullets = {}
        target_role = ""

        if analysis and analysis.report:
            # A3: only keywords the user confirmed they actually have reach
            # the export — raw missing keywords are never injected blind.
            confirmed_keywords = analysis.report.get("confirmed_keywords", [])
            rewritten_bullets = analysis.report.get("ai_rewritten_examples", {})

            # Fetch the job title. A4: it is only used when the caller asks for
            # it (match_title) — by default the export keeps the resume's own
            # title rather than silently adopting the posting's.
            if analysis.job_id:
                job = self.session.get(JobDescription, analysis.job_id)
                if job:
                    target_role = job.title

        return self.exporter.export_tailored(
            sections=resume.parsed_data.get("sections", {}),
            missing_keywords=confirmed_keywords,
            rewritten_bullets=rewritten_bullets,
            target_role=target_role,
            match_title=match_title,
        )

    # ------------------------------------------------------------------ #
    # A3: user-confirmed missing keywords
    # ------------------------------------------------------------------ #

    def confirm_keywords(
        self, resume_id: UUID, analysis_id: UUID, user_id: UUID, keywords: list
    ) -> tuple[list[str], list[str]]:
        """Store the missing keywords the user confirms they actually have.

        Each keyword must belong to this analysis's ``missing_keywords``
        (case-insensitive match, canonical spelling stored) — nothing is
        added to the resume without the user's explicit confirmation.

        Returns ``(confirmed, soft_skipped)``. Soft skills are reported back
        but not stored/exported: a list of adjectives is unverifiable and
        belongs in bullets, not in a skills section.
        """
        resume = self.session.get(Resume, resume_id)
        if not resume or resume.user_id != user_id:
            raise ResumeNotFoundError()
        analysis = self.session.get(ResumeAnalysis, analysis_id)
        if not analysis or analysis.resume_id != resume_id:
            raise AnalysisNotFoundError()

        missing = (analysis.report or {}).get("keyword_analysis", {}).get(
            "missing_keywords", []
        )
        canonical = {m.lower(): m for m in missing}

        confirmed: list[str] = []
        seen: set[str] = set()
        unknown: list[str] = []
        for kw in keywords:
            cleaned = str(kw).strip()
            match = canonical.get(cleaned.lower())
            if not match:
                unknown.append(cleaned)
                continue
            if match.lower() in seen:
                continue
            seen.add(match.lower())
            confirmed.append(match)

        if unknown:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Not in this analysis's missing keywords: "
                    + ", ".join(unknown)
                ),
            )

        soft_skipped = [kw for kw in confirmed if is_soft_skill(kw)]
        confirmed = [kw for kw in confirmed if not is_soft_skill(kw)]
        if not confirmed:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Soft skills aren't added to the Skills section — show "
                    "them in your bullets where you actually used them."
                ),
            )

        report = analysis.report or {}
        # Build a NEW dict: reassigning the same object after an in-place
        # mutation is invisible to SQLAlchemy's change detection, so the JSON
        # column was silently NOT updated — the API returned 200 and the UI
        # showed confirmed chips, but exports (and fresh sessions) never saw
        # them. Caught live: two analyses had confirmed chips and `None` in DB.
        analysis.report = {
            **report,
            "confirmed_keywords": confirmed,
        }
        self.session.add(analysis)
        self.session.commit()
        self.session.refresh(analysis)
        return confirmed, soft_skipped

    # ------------------------------------------------------------------ #
    # D3: per-job tailored resume versions
    # ------------------------------------------------------------------ #

    @classmethod
    def _applied_rewrites_from_report(cls, report: dict) -> dict[str, str]:
        """Only rewrites that actually changed a bullet count as applied —
        withheld or guard-rejected ones are identical to the original and
        must not be claimed (same rule as the D1 improvement scoring)."""
        return {
            orig: opt["ai_output"]
            for orig, opt in (report.get("ai_rewritten_examples") or {}).items()
            if isinstance(opt, dict)
            and opt.get("ai_output")
            and opt["ai_output"].strip() != orig.strip()
        }

    @classmethod
    def _tailored_sections(cls, sections: dict, applied: dict[str, str]) -> dict:
        """Apply rewrites to every shape a section can take: raw strings
        ({"experience": {"raw": ...}}) and parsed bullet lists
        ({"experience_parsed": [{...bullets}]})."""
        tailored = {**sections}
        for key in ("experience", "projects"):
            block = tailored.get(key)
            if isinstance(block, dict) and block.get("raw"):
                raw = block["raw"]
                for orig, repl in applied.items():
                    raw = cls._replace_bullet_text(raw, orig, repl)
                tailored[key] = {**block, "raw": raw}
        for key in ("experience_parsed", "projects_parsed"):
            entries = tailored.get(key)
            if isinstance(entries, list):
                tailored[key] = [
                    {**entry, "bullets": [applied.get(b, b) for b in entry.get("bullets", [])]}
                    for entry in entries
                ]
        return tailored

    def create_version(self, resume_id: UUID, user_id: UUID, analysis_id: UUID) -> ResumeVersion:
        resume = self.session.get(Resume, resume_id)
        if not resume or resume.user_id != user_id:
            raise ResumeNotFoundError()

        analysis = self.session.get(ResumeAnalysis, analysis_id)
        if not analysis or analysis.resume_id != resume_id:
            raise AnalysisNotFoundError()

        applied = self._applied_rewrites_from_report(analysis.report or {})
        if not applied:
            # Honesty: a "tailored version" with zero changed bullets would be
            # an identical copy -- nothing to store.
            raise HTTPException(
                status_code=400,
                detail="No rewrites were applied in this analysis, so there is nothing to save as a version yet.",
            )

        tailored_text = resume.raw_text
        for orig, repl in applied.items():
            tailored_text = self._replace_bullet_text(tailored_text, orig, repl)

        job = self.session.get(JobDescription, analysis.job_id) if analysis.job_id else None
        label = f"Tailored for {job.title}" if job else "Tailored version"

        # Upsert per (resume, job): re-saving after a better analysis replaces
        # the previous version for that job instead of piling up duplicates.
        existing = self.session.exec(
            select(ResumeVersion).where(
                ResumeVersion.resume_id == resume_id,
                ResumeVersion.job_id == analysis.job_id,
            )
        ).first()

        if existing:
            existing.analysis_id = analysis.id
            existing.label = label
            existing.raw_text = tailored_text
            existing.parsed_data = {"sections": self._tailored_sections(resume.parsed_data.get("sections", {}), applied)}
            existing.applied_rewrites = applied
            existing.created_at = datetime.now(timezone.utc)
            self.session.add(existing)
            self.session.commit()
            self.session.refresh(existing)
            return existing

        version = ResumeVersion(
            resume_id=resume_id,
            job_id=analysis.job_id,
            analysis_id=analysis.id,
            label=label,
            raw_text=tailored_text,
            parsed_data={"sections": self._tailored_sections(resume.parsed_data.get("sections", {}), applied)},
            applied_rewrites=applied,
        )
        self.session.add(version)
        self.session.commit()
        self.session.refresh(version)
        return version

    def list_versions(self, resume_id: UUID, user_id: UUID) -> list[ResumeVersion]:
        resume = self.session.get(Resume, resume_id)
        if not resume or resume.user_id != user_id:
            raise ResumeNotFoundError()
        return self.session.exec(
            select(ResumeVersion)
            .where(ResumeVersion.resume_id == resume_id)
            .order_by(ResumeVersion.created_at.desc())
        ).all()

    def delete_version(self, resume_id: UUID, version_id: UUID, user_id: UUID) -> None:
        resume = self.session.get(Resume, resume_id)
        if not resume or resume.user_id != user_id:
            raise ResumeNotFoundError()
        version = self.session.get(ResumeVersion, version_id)
        if not version or version.resume_id != resume_id:
            raise VersionNotFoundError()
        self.session.delete(version)
        self.session.commit()

    def export_version_docx(
        self,
        resume_id: UUID,
        version_id: UUID,
        user_id: UUID,
        match_title: bool = False,
    ) -> tuple[bytes, str]:
        """Export the stored tailored version. Bullets are already rewritten in
        the stored sections, so no rewrite map is passed to the exporter."""
        resume = self.session.get(Resume, resume_id)
        if not resume or resume.user_id != user_id:
            raise ResumeNotFoundError()
        version = self.session.get(ResumeVersion, version_id)
        if not version or version.resume_id != resume_id:
            raise VersionNotFoundError()

        analysis = self.session.get(ResumeAnalysis, version.analysis_id)
        confirmed_keywords = []
        target_role = ""
        if analysis and analysis.report:
            # A3: confirmed keywords only — same rule as export_docx.
            confirmed_keywords = analysis.report.get("confirmed_keywords", [])
        if version.job_id:
            job = self.session.get(JobDescription, version.job_id)
            if job:
                target_role = job.title

        data = self.exporter.export_tailored(
            sections=version.parsed_data.get("sections", {}),
            missing_keywords=confirmed_keywords,
            rewritten_bullets={},
            target_role=target_role,
            match_title=match_title,
        )
        # A4: name the file after the job only when the export actually used
        # the job's title; otherwise the filename would imply a match that
        # isn't in the document.
        safe = (
            re.sub(r"[^A-Za-z0-9]+", "_", target_role).strip("_")
            if match_title and target_role
            else ""
        )
        filename = f"Resume_Tailored_{safe}.docx" if safe else "ATS_Optimized_Resume.docx"
        return data, filename
