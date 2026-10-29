from sqlmodel import Session, select
from uuid import UUID, uuid4
from datetime import datetime, timezone
from functools import lru_cache
from fastapi import UploadFile, HTTPException
import os
import re

from app.config.settings import get_settings
from app.resume.models import Resume, ResumeAnalysis, ResumeVersion
from app.jobs.models import JobDescription
from app.parser.text_extractor import TextExtractor
from app.parser.section_parser import SectionParser
from app.analyzer.ats_checker import ATSCompatibilityChecker
from app.analyzer.keyword_engine import KeywordEngine
from app.analyzer.bullet_analyzer import BulletAnalyzer
from app.analyzer.grammar_checker import GrammarChecker
from app.analyzer.ai_rewriter import AIRewriter, MAX_BULLETS_PER_CALL
from app.analyzer.scoring import compute_overall
from app.export.docx_exporter import DocxExporter
from app.export.pdf_exporter import PdfExporter
from app.export.content import ResumeContentBuilder
from app.common.exceptions import AnalysisNotFoundError, JobNotFoundError, ResumeNotFoundError, VersionNotFoundError
from app.common.skills import is_soft_skill

# C6: rewrites are applied only after the user accepts them. An unfilled
# placeholder ("[X]") must never reach the document — the exporter refuses
# them too, but blocking at review time lets us tell the user why.
_PLACEHOLDER_RE = re.compile(r"\[[^\]]{1,30}\]")
MAX_REWRITE_CHARS = 600

# How many flagged bullets we'll attempt to send for AI rewriting per analysis.
# AIRewriter.MAX_BULLETS_PER_CALL caps what actually goes in the API request;
# this just bounds how many we try to flag in the first place.
MAX_BULLETS_TO_REWRITE = 8


@lru_cache(maxsize=1)
def _shared_components() -> dict:
    """C5/F6: build the analyzers and AI client once for the whole process.

    ``AIRewriter`` resolves its provider/model/key at construction time and
    creates one OpenAI client; rebuilding it per request threw that away and
    re-read settings every time. The analyzers are stateless, so sharing them
    is safe. Call ``clear_shared_components()`` in tests that need a fresh
    configuration.
    """
    return {
        "extractor": TextExtractor(),
        "sec_parser": SectionParser(),
        "ats_checker": ATSCompatibilityChecker(),
        "kw_engine": KeywordEngine(),
        "bullet_analyzer": BulletAnalyzer(),
        "grammar": GrammarChecker(),
        "ai": AIRewriter(),
        "exporter": DocxExporter(),
        "pdf_exporter": PdfExporter(),
        "content": ResumeContentBuilder(),
    }


def clear_shared_components() -> None:
    """Drop the shared analyzers (tests / config reloads)."""
    _shared_components.cache_clear()


def shared_ai_rewriter() -> AIRewriter:
    """The process-wide AI client, shared by analysis and cover letters."""
    return _shared_components()["ai"]


class ResumeService:
    def __init__(self, session: Session):
        self.session = session
        # C5/F6: the analyzers (notably the grammar SpellChecker and the AI
        # client) are expensive to build and hold no per-request state, so one
        # shared set is created lazily and reused by every request instead of
        # being rebuilt for each ResumeService instance.
        components = _shared_components()
        self.extractor = components["extractor"]
        self.sec_parser = components["sec_parser"]
        self.ats_checker = components["ats_checker"]
        self.kw_engine = components["kw_engine"]
        self.bullet_analyzer = components["bullet_analyzer"]
        self.grammar = components["grammar"]
        self.ai = components["ai"]
        self.exporter = components["exporter"]
        self.pdf_exporter = components["pdf_exporter"]
        self.content = components["content"]

    def upload(self, file: UploadFile, user_id: UUID) -> Resume:
        if not file.filename:
            raise HTTPException(status_code=400, detail="File name is required")

        settings = get_settings()
        # A6: never trust the client's filename as a path. Only the extension
        # is kept (validated against the allowlist); the file is stored under a
        # random name inside the user's own upload directory. The display name
        # is sanitized separately so traversal sequences cannot reach the UI.
        ext = os.path.splitext(file.filename)[1].lower()
        allowed = [e.lower() for e in settings.allowed_extensions]
        if ext not in allowed:
            shown = ext or "no extension"
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported file type ({shown}). "
                    f"Allowed types: {', '.join(allowed)}."
                ),
            )

        # A7: enforce the configured size cap before parsing or writing. Read
        # one byte past the limit so an oversized upload is rejected without
        # ever loading the whole file into memory.
        max_bytes = settings.max_file_size_mb * 1024 * 1024
        file_bytes = file.file.read(max_bytes + 1)
        if len(file_bytes) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"File is too large. The maximum size is "
                    f"{settings.max_file_size_mb} MB."
                ),
            )
        if not file_bytes:
            raise HTTPException(status_code=400, detail="The uploaded file is empty.")

        filename = self._safe_display_name(file.filename, ext)
        extracted = self.extractor.extract(file_bytes, ext)
        parsed = self.sec_parser.parse(extracted["raw_text"])

        user_dir = os.path.join(settings.upload_dir, str(user_id))
        os.makedirs(user_dir, exist_ok=True)
        path = os.path.join(user_dir, f"{uuid4().hex}{ext}")
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

    @staticmethod
    def _safe_display_name(name: str, ext: str) -> str:
        """Strip directories/control characters so only a safe label remains."""
        base = os.path.basename(name.replace("\\", "/")).strip()
        base = re.sub(r"[\x00-\x1f\x7f]", "", base)
        base = re.sub(r"\s+", " ", base)
        stem = os.path.splitext(base)[0].strip(" .")
        stem = re.sub(r"[<>:\"/\\|?*]", "", stem).strip(" .")
        if len(stem) > 100:
            stem = stem[:100].rstrip(" .")
        return f"{stem or 'resume'}{ext}"

    def analyze(
        self,
        resume_id: UUID,
        user_id: UUID,
        job_id: UUID | None = None,
        use_ai: bool = True,
    ) -> ResumeAnalysis:
        resume = self.session.get(Resume, resume_id)
        if not resume or resume.user_id != user_id:
            raise ResumeNotFoundError()

        sections = resume.parsed_data.get("sections", {})
        meta = resume.parsed_data.get("metadata", {})

        # B9: the stored filename lets the checker flag ATS-hostile names
        # (spaces, special characters) without re-reading the upload.
        ats_res = self.ats_checker.check(
            resume.raw_text, sections, meta, filename=resume.filename
        )
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
            # B8: use D2's required/preferred buckets so must-have skills
            # weigh more than nice-to-have ones. Jobs parsed before D2 have
            # no buckets, which falls back to plain coverage.
            job_keywords = job_obj.extracted_keywords or {}
            kw_res = self.kw_engine.analyze(
                resume.raw_text,
                job_obj.raw_text,
                required_skills=job_keywords.get("required_skills"),
                preferred_skills=job_keywords.get("preferred_skills"),
            )

        # B10: grammar is now part of the overall score (it was computed but
        # discarded). Unavailable components (no job => no keywords) are
        # dropped and the remaining weights are rescaled.
        overall, weights_used = compute_overall({
            "ats": ats_res["score"],
            "bullets": bullet_res["score"],
            "keywords": kw_res["score"],
            "grammar": grammar_res["score"],
        })

        # AI rewrite for weak/metric-less bullets, batched into ONE API call instead of
        # one call per bullet. Truthfulness rules (no invented numbers/tools) live in AIRewriter.
        flagged = [
            b["original"] for b in bullet_res.get("details", [])
            if not b["has_metrics"] or b["verb_type"] == "weak"
        ][:MAX_BULLETS_TO_REWRITE]

        # E4: AI rewriting is opt-out. Resume text may only leave the machine
        # when the server switch is on AND the user asked for it. The rest of
        # the analysis (ATS, bullets, keywords, grammar) is always local.
        ai_info = {
            "enabled": False,
            "reason": "no_flagged_bullets",
            "flagged_bullets": len(flagged),
            "bullets_sent": 0,
            "provider": None,
            "model": None,
        }
        rewritten: dict = {}
        if flagged:
            if not get_settings().ai_rewriting_enabled:
                ai_info["reason"] = "disabled_by_server"
            elif not use_ai:
                ai_info["reason"] = "disabled_by_user"
            elif getattr(self.ai, "client", None) is None:
                # No key configured: the rewriter would only return fallbacks.
                ai_info["reason"] = "not_configured"
            else:
                rewritten = self.ai.rewrite_bullets(
                    flagged,
                    target_role=target_role,
                    matched_keywords=kw_res.get("matched_keywords", []),
                    missing_keywords=kw_res.get("missing_keywords", []),
                )
                ai_info.update({
                    "enabled": True,
                    "reason": "ran",
                    # MAX_BULLETS_PER_CALL caps what actually goes in the request.
                    "bullets_sent": min(len(flagged), MAX_BULLETS_PER_CALL),
                    "provider": self._ai_name("provider"),
                    "model": self._ai_name("model"),
                })

        # D1: before/after re-scoring — re-run the analyzers on the tailored
        # text (only rewrites that actually changed a bullet) so the report can
        # show the projected improvement honestly.
        improvement = self._score_improvement(
            resume, bullet_entries, bullet_res, kw_res, ats_res, grammar_res,
            overall, rewritten, job_obj,
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
                # E4: what happened to the AI step, so the UI can say whether
                # any resume text left the machine and why.
                "ai_rewriting": ai_info,
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

    def _ai_name(self, attribute: str) -> str | None:
        """Provider/model name for the report, or None when unavailable."""
        value = getattr(self.ai, attribute, None)
        return value if isinstance(value, str) and value else None

    def _score_improvement(
        self,
        resume: Resume,
        bullet_entries: list,
        before_bullets: dict,
        before_keywords: dict,
        ats_res: dict,
        grammar_res: dict,
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
            after_keywords = self.kw_engine.analyze(
                tailored_text,
                job_obj.raw_text,
                # B8: the before-score is weighted, so the after-score must be
                # too — otherwise the improvement comparison is not like-for-like.
                required_skills=(job_obj.extracted_keywords or {}).get("required_skills"),
                preferred_skills=(job_obj.extracted_keywords or {}).get("preferred_skills"),
            )

        # ATS compatibility and grammar are text/format-based: bullet rewrites
        # don't change them, so they carry over unchanged rather than being
        # faked as improved. Including them keeps the before/after overall
        # scores on the same B10 weighting.
        after_overall, _ = compute_overall({
            "ats": ats_res["score"],
            "bullets": after_bullets.get("score"),
            "keywords": (after_keywords or {}).get("score"),
            "grammar": grammar_res.get("score"),
        })

        return {
            "applied_rewrites": len(applied),
            "flagged_bullets": len(rewritten),
            "before": {
                "overall": before_overall,
                "bullets": before_bullets.get("score"),
                "keywords": before_keywords.get("score"),
                "grammar": grammar_res.get("score"),
            },
            "after": {
                "overall": after_overall,
                "bullets": after_bullets.get("score"),
                "keywords": (after_keywords or {}).get("score"),
                "grammar": grammar_res.get("score"),
            },
        }

    def get_analysis(self, resume_id: UUID, analysis_id: UUID, user_id: UUID) -> ResumeAnalysis:
        """F8: fetch one stored analysis by id so the UI can reload it after a
        refresh instead of relying on sessionStorage."""
        resume = self.session.get(Resume, resume_id)
        if not resume or resume.user_id != user_id:
            raise ResumeNotFoundError()
        analysis = self.session.get(ResumeAnalysis, analysis_id)
        if not analysis or analysis.resume_id != resume_id:
            raise AnalysisNotFoundError()
        return analysis

    # ------------------------------------------------------------------ #
    # D6: original vs. tailored comparison
    # ------------------------------------------------------------------ #

    def get_comparison(
        self, resume_id: UUID, analysis_id: UUID, user_id: UUID
    ) -> dict:
        """Return the original resume and the exact tailored content an export
        would produce, plus the accepted rewrites that changed it.

        The tailored view is built from ``_tailored_sections`` and the same
        confirmed-keyword rules the exporters use, so nothing shown here is a
        promise the download won't keep.
        """
        resume = self.session.get(Resume, resume_id)
        if not resume or resume.user_id != user_id:
            raise ResumeNotFoundError()
        analysis = self.session.get(ResumeAnalysis, analysis_id)
        if not analysis or analysis.resume_id != resume_id:
            raise AnalysisNotFoundError()

        report = analysis.report or {}
        sections = resume.parsed_data.get("sections", {}) or {}
        accepted = self._decided_rewrites(report)
        confirmed = report.get("confirmed_keywords", []) or []
        tailored_sections = self._tailored_sections(sections, accepted)

        job_title = None
        if analysis.job_id:
            job = self.session.get(JobDescription, analysis.job_id)
            if job:
                job_title = job.title

        return {
            "resume_id": str(resume_id),
            "analysis_id": str(analysis_id),
            "job_title": job_title,
            "original": self._comparison_view(sections, [], None),
            "tailored": self._comparison_view(
                tailored_sections, confirmed, accepted
            ),
            "changes": [
                {"original": original, "tailored": replacement}
                for original, replacement in accepted.items()
                if self._rewrite_is_in_sections(original, sections)
            ],
            "confirmed_keywords": self._exported_confirmed_keywords(
                sections, confirmed
            ),
        }

    def _comparison_view(
        self,
        sections: dict,
        keywords: list[str],
        rewritten: dict[str, str] | None,
    ) -> dict:
        """Flatten one version of the resume into heading + display lines.

        Parsed bullets stay 1:1 (unlike the exporters, which merge accidental
        continuations) so a changed bullet is easy to spot side by side.
        """
        content = self.content
        contact = sections.get("contact_parsed", {}) or {}
        view = {
            "header": {
                "name": (contact.get("name") or "").strip(),
                "title": content.resume_title(sections),
                "contact": [
                    text for _, text in content.contact_parts(contact)
                ],
            },
            "sections": [],
        }

        def add(key: str, heading: str, lines: list[str]):
            cleaned = [line for line in lines if (line or "").strip()]
            if cleaned:
                view["sections"].append(
                    {"key": key, "heading": heading, "lines": cleaned}
                )

        summary_raw = (sections.get("summary") or {}).get("raw")
        if summary_raw:
            text = content.summary_text(summary_raw)
            if text:
                add("summary", "SUMMARY", [text])

        education_parsed = sections.get("education_parsed")
        education_raw = (sections.get("education") or {}).get("raw")
        education_lines: list[str] = []
        if education_parsed:
            for entry in education_parsed:
                parts = content.education_parts(entry)
                if not parts["primary"]:
                    continue
                line = parts["primary"]
                if parts["dates"]:
                    line += f"  |  {parts['dates']}"
                education_lines.append(line)
                if parts["secondary"]:
                    education_lines.append(parts["secondary"])
                education_lines.extend(parts["details"])
        elif education_raw:
            education_lines = content._clean_lines(education_raw)
        add("education", "EDUCATION", education_lines)

        skills_raw = (sections.get("skills") or {}).get("raw")
        if skills_raw:
            skill_lines, leftover = content.skills_lines(skills_raw, keywords)
            if leftover:
                skill_lines.append("Additional Skills: " + ", ".join(leftover))
            add("skills", "TECHNICAL SKILLS", skill_lines)

        for key, parsed_key, heading in (
            ("experience", "experience_parsed", "EXPERIENCE"),
            ("projects", "projects_parsed", "PROJECTS"),
        ):
            parsed = sections.get(parsed_key)
            raw = (sections.get(key) or {}).get("raw")
            lines: list[str] = []
            if parsed:
                for entry in parsed:
                    parts = content.entry_parts(entry)
                    header = parts["title"]
                    if parts["subtitle"]:
                        header += f" — {parts['subtitle']}"
                    if parts["dates"]:
                        header += f"  |  {parts['dates']}"
                    if header:
                        lines.append(header)
                    for text in content.entry_bullet_texts(
                        entry.get("bullets") or [], rewritten
                    ):
                        lines.append(f"• {text}")
            elif raw:
                lines = content._clean_lines(raw)
            add(key, heading, lines)

        for key, heading in (
            ("certifications", "CERTIFICATIONS"),
            ("languages", "LANGUAGES"),
        ):
            raw = (sections.get(key) or {}).get("raw")
            if raw:
                add(key, heading, content._clean_lines(raw))

        return view

    @staticmethod
    def _rewrite_is_in_sections(original: str, sections: dict) -> bool:
        """True when an accepted rewrite points at a bullet this resume has."""
        for key in ("experience_parsed", "projects_parsed"):
            for entry in sections.get(key) or []:
                if original in (entry.get("bullets") or []):
                    return True
        for key in ("experience", "projects"):
            raw = (sections.get(key) or {}).get("raw") or ""
            if original in raw:
                return True
        return False

    def _exported_confirmed_keywords(
        self, sections: dict, confirmed: list[str]
    ) -> list[str]:
        """The confirmed keywords that will actually appear in the export."""
        if not confirmed:
            return []
        skills_raw = (sections.get("skills") or {}).get("raw") or ""
        if not skills_raw:
            # The exporters only add confirmed skills to an existing Skills
            # section; without one there is nothing to fold them into.
            return []
        return self.content._filter_keywords(skills_raw, confirmed)

    def _export_payload(
        self,
        resume_id: UUID,
        user_id: UUID,
        analysis_id: UUID | None = None,
    ) -> tuple[dict, list[str], dict[str, str], str]:
        """Load everything an export needs: sections, confirmed skills, the
        accepted rewrites, and the job title (used only with ``match_title``).

        DOCX and PDF share this so the two files always say the same thing.
        """
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
            statement = (
                select(ResumeAnalysis)
                .where(ResumeAnalysis.resume_id == resume_id)
                .order_by(ResumeAnalysis.created_at.desc())
            )
            analysis = self.session.exec(statement).first()

        confirmed_keywords: list[str] = []
        rewritten_bullets: dict[str, str] = {}
        target_role = ""

        if analysis and analysis.report:
            # A3: only keywords the user confirmed they actually have reach
            # the export — raw missing keywords are never injected blind.
            confirmed_keywords = analysis.report.get("confirmed_keywords", [])
            # C6: only rewrites the user accepted (or edited) reach the export.
            # A fresh analysis applies none: the original bullets are exported
            # until the user reviews the suggestions.
            rewritten_bullets = self._decided_rewrites(analysis.report)

            # Fetch the job title. A4: it is only used when the caller asks for
            # it (match_title) — by default the export keeps the resume's own
            # title rather than silently adopting the posting's.
            if analysis.job_id:
                job = self.session.get(JobDescription, analysis.job_id)
                if job:
                    target_role = job.title

        return (
            resume.parsed_data.get("sections", {}) or {},
            confirmed_keywords,
            rewritten_bullets,
            target_role,
        )

    def export_docx(
        self,
        resume_id: UUID,
        user_id: UUID,
        analysis_id: UUID | None = None,
        match_title: bool = False,
    ) -> bytes:
        sections, keywords, rewrites, target_role = self._export_payload(
            resume_id, user_id, analysis_id
        )
        return self.exporter.export_tailored(
            sections=sections,
            missing_keywords=keywords,
            rewritten_bullets=rewrites,
            target_role=target_role,
            match_title=match_title,
        )

    def export_pdf(
        self,
        resume_id: UUID,
        user_id: UUID,
        analysis_id: UUID | None = None,
        match_title: bool = False,
    ) -> bytes:
        """D5: same content as the DOCX export, rendered as a text PDF."""
        sections, keywords, rewrites, target_role = self._export_payload(
            resume_id, user_id, analysis_id
        )
        return self.pdf_exporter.export_tailored(
            sections=sections,
            missing_keywords=keywords,
            rewritten_bullets=rewrites,
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
    # C6: user review of AI rewrites
    # ------------------------------------------------------------------ #

    @classmethod
    def _decided_rewrites(cls, report: dict) -> dict[str, str]:
        """The rewrites the user accepted, ready for the exporter.

        Nothing is applied by default: a fresh analysis has no decisions, so
        the export keeps the original bullets until the user reviews them.
        Rejected suggestions and unfilled placeholders are never applied.
        """
        decisions = report.get("rewrite_decisions") or {}
        out: dict[str, str] = {}
        for original, decision in decisions.items():
            if not isinstance(decision, dict):
                continue
            if decision.get("action") != "accepted":
                continue
            text = str(decision.get("text") or "").strip()
            if not text or text == str(original).strip():
                continue
            if _PLACEHOLDER_RE.search(text):
                continue
            out[original] = text
        return out

    def confirm_rewrites(
        self,
        resume_id: UUID,
        analysis_id: UUID,
        user_id: UUID,
        decisions: list,
    ) -> tuple[dict, int]:
        """Store the user's accept/reject/edit decision per AI rewrite.

        Decisions merge by original bullet, so the UI can save one card at a
        time. Only accepted (or edited) rewrites are applied to the export;
        rejecting a suggestion keeps the original bullet.

        Returns ``(rewrite_decisions, applied_count)``.
        """
        resume = self.session.get(Resume, resume_id)
        if not resume or resume.user_id != user_id:
            raise ResumeNotFoundError()
        analysis = self.session.get(ResumeAnalysis, analysis_id)
        if not analysis or analysis.resume_id != resume_id:
            raise AnalysisNotFoundError()

        examples = (analysis.report or {}).get("ai_rewritten_examples") or {}
        suggestions = {
            original: opt for original, opt in examples.items()
            if isinstance(opt, dict)
        }

        updates: dict[str, dict | None] = {}
        unknown: list[str] = []
        invalid: list[str] = []
        for item in decisions:
            if not isinstance(item, dict):
                raise HTTPException(
                    status_code=400, detail="Each decision must be an object"
                )
            original = str(item.get("original") or "").strip()
            action = str(item.get("action") or "").strip().lower()
            if original not in suggestions:
                unknown.append(original)
                continue
            if action == "pending":
                # Undo: drop the decision so the card is unreviewed again and
                # the export keeps the original bullet.
                updates[original] = None
                continue
            if action not in ("accepted", "rejected"):
                invalid.append(
                    f"{original}: action must be 'accepted', 'rejected' or 'pending'"
                )
                continue
            if action == "rejected":
                updates[original] = {"action": "rejected", "text": ""}
                continue

            text = str(item.get("text") or "").strip()
            if not text:
                # "Accept" without an edit applies the moderate rewrite.
                text = str(suggestions[original].get("ai_output") or "").strip()
            placeholder = _PLACEHOLDER_RE.search(text)
            if placeholder:
                # C6: a rewrite with an unfilled "[X]" must never be accepted —
                # that is exactly the download-time surprise this item exists
                # to prevent.
                invalid.append(
                    f"{original}: fill in the {placeholder.group(0)} "
                    "placeholder before accepting this rewrite"
                )
                continue
            if not text:
                invalid.append(f"{original}: there is no rewrite text to accept")
                continue
            if len(text) > MAX_REWRITE_CHARS:
                invalid.append(
                    f"{original}: rewrite is too long "
                    f"(max {MAX_REWRITE_CHARS} characters)"
                )
                continue
            updates[original] = {"action": "accepted", "text": text}

        if unknown:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Not an AI rewrite in this analysis: " + ", ".join(unknown)
                ),
            )
        if invalid:
            raise HTTPException(status_code=400, detail="; ".join(invalid))
        if not updates:
            raise HTTPException(status_code=400, detail="No rewrite decisions to save")

        report = analysis.report or {}
        # New dict object, same reason as confirm_keywords: in-place mutation is
        # invisible to SQLAlchemy's JSON change detection.
        merged = {
            key: value
            for key, value in {
                **(report.get("rewrite_decisions") or {}),
                **updates,
            }.items()
            if value is not None
        }
        analysis.report = {**report, "rewrite_decisions": merged}
        self.session.add(analysis)
        self.session.commit()
        self.session.refresh(analysis)
        return merged, len(self._decided_rewrites(analysis.report))

    # ------------------------------------------------------------------ #
    # D3: per-job tailored resume versions
    # ------------------------------------------------------------------ #

    @classmethod
    def _applied_rewrites_from_report(cls, report: dict) -> dict[str, str]:
        """D3: the rewrites to bake into a saved version.

        C6: a version is built from the rewrites the user accepted, not from
        every suggestion the model produced — otherwise saving a version would
        silently apply text the user never approved.
        """
        return cls._decided_rewrites(report)

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
            # an identical copy -- nothing to store. C6: rewrites only count
            # once the user accepts them.
            raise HTTPException(
                status_code=400,
                detail=(
                    "No AI rewrites have been accepted for this analysis yet. "
                    "Review the suggestions and accept the ones you want before "
                    "saving a version."
                ),
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

    def _version_export_payload(
        self,
        resume_id: UUID,
        version_id: UUID,
        user_id: UUID,
    ) -> tuple[dict, list[str], str]:
        """Load the stored tailored sections and export metadata for a version."""
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

        return (
            version.parsed_data.get("sections", {}) or {},
            confirmed_keywords,
            target_role,
        )

    @staticmethod
    def _version_filename(
        target_role: str, match_title: bool, extension: str
    ) -> str:
        # A4: name the file after the job only when the export actually used
        # the job's title; otherwise the filename would imply a match that
        # isn't in the document.
        safe = (
            re.sub(r"[^A-Za-z0-9]+", "_", target_role).strip("_")
            if match_title and target_role
            else ""
        )
        if safe:
            return f"Resume_Tailored_{safe}.{extension}"
        return f"ATS_Optimized_Resume.{extension}"

    def export_version_docx(
        self,
        resume_id: UUID,
        version_id: UUID,
        user_id: UUID,
        match_title: bool = False,
    ) -> tuple[bytes, str]:
        """Export the stored tailored version. Bullets are already rewritten in
        the stored sections, so no rewrite map is passed to the exporter."""
        sections, confirmed_keywords, target_role = self._version_export_payload(
            resume_id, version_id, user_id
        )
        data = self.exporter.export_tailored(
            sections=sections,
            missing_keywords=confirmed_keywords,
            rewritten_bullets={},
            target_role=target_role,
            match_title=match_title,
        )
        return data, self._version_filename(target_role, match_title, "docx")

    def export_version_pdf(
        self,
        resume_id: UUID,
        version_id: UUID,
        user_id: UUID,
        match_title: bool = False,
    ) -> tuple[bytes, str]:
        """D5: the same stored version rendered as a text PDF."""
        sections, confirmed_keywords, target_role = self._version_export_payload(
            resume_id, version_id, user_id
        )
        data = self.pdf_exporter.export_tailored(
            sections=sections,
            missing_keywords=confirmed_keywords,
            rewritten_bullets={},
            target_role=target_role,
            match_title=match_title,
        )
        return data, self._version_filename(target_role, match_title, "pdf")
