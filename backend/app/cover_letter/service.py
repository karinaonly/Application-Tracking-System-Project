"""D8: cover-letter generation from the candidate's real resume facts.

Privacy and honesty rules:

* Only selected facts leave the machine (name, headline, summary, a capped set
  of experience bullets, skills, and the job posting). Email, phone, location,
  and links are never included.
* The letter is generated only when the user explicitly asks for it, and only
  when the server's AI switch is on.
* A heuristic guard rejects placeholders, numbers, and skills that are not in
  the resume facts; one retry is attempted, then the draft is returned flagged
  for review rather than silently presented as safe.
"""

import json
import re
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session

from app.analyzer.claim_guard import PLACEHOLDER_PATTERN, check_rewrite
from app.config.settings import get_settings
from app.common.exceptions import JobNotFoundError, ResumeNotFoundError
from app.cover_letter.schemas import CoverLetterTone
from app.jobs.models import JobDescription
from app.resume.models import Resume
from app.resume.service import shared_ai_rewriter

MAX_SUMMARY_CHARS = 700
MAX_BULLETS = 8
MAX_BULLET_CHARS = 300
MAX_SKILLS = 15
MAX_JD_CHARS = 3500
MIN_WORDS = 100
MAX_WORDS = 600
MAX_GUARD_DETAILS = 5

_FENCE_RE = re.compile(r"^```(?:markdown|text|md)?\s*|\s*```$", re.I | re.M)
_BAD_DASH_RE = re.compile(r"[\u2010\u2011\u2012\u2015\u2212\uFE58\uFE63\u00AD\uFFFD]")

_TONE_INSTRUCTIONS = {
    "professional": "Direct and professional. Specific, calm, no hype.",
    "enthusiastic": "Warm and enthusiastic, but still factual. No exclamation-mark spam.",
    "concise": "Under 250 words, three short paragraphs, no filler.",
}

_SYSTEM_PROMPT = (
    "You write cover letters for job applications. Use ONLY the facts in the "
    "CANDIDATE FACTS section.\n\n"
    "HARD RULES (never break these):\n"
    "1. NEVER invent an employer, job title, date, degree, certification, metric, "
    "percentage, dollar amount, team size, or achievement.\n"
    "2. NEVER claim a skill, tool, or technology that is not listed in the "
    "candidate facts, even if the job asks for it.\n"
    "3. NEVER add placeholders such as [X], TBD, or blank underscores.\n"
    "4. Do not invent a referral, a personal connection, or knowledge of the "
    "company beyond the job posting.\n"
    "5. Do not use hype: no 'world-class', 'cutting-edge', 'guaranteed', "
    "'seamless', 'revolutionary', or vague magnitude claims.\n"
    "6. Plain text only: no markdown, no bullet lists, no tables, no address block.\n"
    "7. 250-350 words, three or four paragraphs. Start with 'Dear Hiring Manager,' "
    "and end with 'Sincerely,' followed by the candidate's name if one is provided.\n\n"
    "If the facts are thin, write a shorter, honest letter rather than inventing "
    "experience. Return only the letter text."
)


def _one_line(value: object, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit].rstrip()


def _clean_output(text: str) -> str:
    cleaned = _FENCE_RE.sub("", text.strip()).strip()
    cleaned = _BAD_DASH_RE.sub("-", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


class CoverLetterService:
    def __init__(self, session: Session, ai=None):
        self.session = session
        self.ai = ai if ai is not None else shared_ai_rewriter()

    # ------------------------------------------------------------------ #
    # Source selection (also returned to the UI before generation)
    # ------------------------------------------------------------------ #
    def _load(self, resume_id, job_id, user_id) -> tuple[Resume, JobDescription]:
        resume = self.session.get(Resume, resume_id)
        if not resume or resume.user_id != user_id:
            raise ResumeNotFoundError()
        job = self.session.get(JobDescription, job_id)
        if not job or job.user_id != user_id:
            raise JobNotFoundError()
        return resume, job

    def _build_source(self, resume: Resume, job: JobDescription) -> dict:
        sections = resume.parsed_data.get("sections", {}) or {}
        contact = sections.get("contact_parsed", {}) or {}
        summary = _one_line((sections.get("summary") or {}).get("raw"), MAX_SUMMARY_CHARS)

        experience = []
        bullets_sent = 0
        for entry in sections.get("experience_parsed", []) or []:
            if bullets_sent >= MAX_BULLETS:
                break
            bullets = []
            for bullet in entry.get("bullets", []) or []:
                if bullets_sent >= MAX_BULLETS:
                    break
                cleaned = _one_line(bullet, MAX_BULLET_CHARS)
                if cleaned:
                    bullets.append(cleaned)
                    bullets_sent += 1
            title = _one_line(entry.get("title"), 120)
            company = _one_line(entry.get("company"), 160)
            if bullets or title or company:
                experience.append({
                    "title": title,
                    "company": company,
                    "dates": _one_line(entry.get("dates"), 80),
                    "bullets": bullets,
                })

        skills = []
        for skill in sections.get("skills_parsed", []) or []:
            cleaned = _one_line(skill, 80)
            if cleaned and cleaned not in skills:
                skills.append(cleaned)
            if len(skills) >= MAX_SKILLS:
                break

        keywords = job.extracted_keywords or {}
        return {
            "candidate": {
                "name": _one_line(contact.get("name"), 120),
                "headline": _one_line(contact.get("title"), 160),
                "summary": summary,
            },
            "experience": experience,
            "skills": skills,
            "job": {
                "title": _one_line(job.title, 160),
                "company": _one_line(job.company, 160),
                "required_skills": [
                    _one_line(skill, 80)
                    for skill in (keywords.get("required_skills") or [])[:MAX_SKILLS]
                ],
                "preferred_skills": [
                    _one_line(skill, 80)
                    for skill in (keywords.get("preferred_skills") or [])[:MAX_SKILLS]
                ],
                "description_excerpt": (job.raw_text or "").strip()[:MAX_JD_CHARS],
            },
            "limits": {
                "experience_bullets": bullets_sent,
                "skills": len(skills),
                "job_description_chars": min(len(job.raw_text or ""), MAX_JD_CHARS),
            },
        }

    def _availability(self) -> tuple[bool, str]:
        if not get_settings().ai_rewriting_enabled:
            return False, "disabled_by_server"
        if getattr(self.ai, "client", None) is None:
            return False, "not_configured"
        return True, "ready"

    def preview(self, resume_id, job_id, user_id) -> dict:
        resume, job = self._load(resume_id, job_id, user_id)
        available, reason = self._availability()
        return {
            "resume_id": str(resume_id),
            "job_id": str(job_id),
            "available": available,
            "reason": reason,
            "provider": getattr(self.ai, "provider", None),
            "model": getattr(self.ai, "model", None),
            "source": self._build_source(resume, job),
        }

    # ------------------------------------------------------------------ #
    # Generation
    # ------------------------------------------------------------------ #
    def generate(
        self,
        resume_id,
        job_id,
        user_id,
        tone: CoverLetterTone = "professional",
    ) -> dict:
        resume, job = self._load(resume_id, job_id, user_id)
        available, reason = self._availability()
        if not available:
            detail = (
                "AI features are disabled on this server (AI_REWRITING_ENABLED=false)."
                if reason == "disabled_by_server"
                else "AI provider is not configured. Add an API key in backend/.env."
            )
            raise HTTPException(status_code=503, detail=detail)

        source = self._build_source(resume, job)
        base_prompt = self._build_prompt(source, tone)
        guard_source = self._guard_source(source)

        text = ""
        reasons: list[str] = []
        retried = False
        for attempt in range(2):
            prompt = base_prompt
            if attempt == 1:
                retried = True
                prompt += (
                    "\n\nYour previous draft was rejected because it "
                    + "; ".join(reasons)
                    + ". Rewrite it using only the CANDIDATE FACTS above."
                )

            raw, error = self.ai.generate_text(_SYSTEM_PROMPT, prompt)
            if error:
                raise HTTPException(
                    status_code=502,
                    detail=f"Cover letter generation failed: {error}",
                )
            text = _clean_output(raw or "")
            reasons = self._guard(text, guard_source)
            words = len(text.split())
            if words < MIN_WORDS:
                reasons.append(f"draft is too short ({words} words)")
            elif words > MAX_WORDS:
                reasons.append(f"draft is too long ({words} words)")
            if not reasons:
                break

        words = len(text.split())
        if not text or words < MIN_WORDS or words > MAX_WORDS:
            raise HTTPException(
                status_code=502,
                detail="The AI returned an unusable cover letter. Please try again.",
            )

        return {
            "text": text,
            "word_count": words,
            "tone": tone,
            "provider": getattr(self.ai, "provider", None),
            "model": getattr(self.ai, "model", None),
            "source": source,
            "guard": {
                "status": "passed" if not reasons else "flagged",
                "reasons": reasons,
                "retried": retried,
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _guard_source(self, source: dict) -> str:
        candidate = source["candidate"]
        parts = [
            candidate["name"],
            candidate["headline"],
            candidate["summary"],
            source["job"]["title"],
            source["job"]["company"],
            str(datetime.now(timezone.utc).year),
        ]
        for entry in source["experience"]:
            parts.extend([entry["title"], entry["company"], entry["dates"]])
            parts.extend(entry["bullets"])
        parts.extend(source["skills"])
        return "\n".join(part for part in parts if part)

    def _guard(self, text: str, guard_source: str) -> list[str]:
        labels = {
            "placeholder": "contains placeholders",
            "new_number": "adds numbers or quantities not in your resume",
            "new_skill": "claims skills not in your resume",
        }
        reasons = []
        for code, details in check_rewrite(guard_source, text):
            if code not in labels:
                continue
            shown = ", ".join(str(item) for item in details[:MAX_GUARD_DETAILS])
            reasons.append(f"{labels[code]}: {shown}")
        if not reasons and PLACEHOLDER_PATTERN.search(text):
            # check_rewrite only reports placeholders absent from the source;
            # a placeholder in a letter is never acceptable.
            reasons.append("contains placeholders")
        return reasons

    def _build_prompt(self, source: dict, tone: CoverLetterTone) -> str:
        candidate = source["candidate"]
        job = source["job"]
        lines = ["CANDIDATE FACTS", f"Name: {candidate['name'] or '(not provided)'}"]
        if candidate["headline"]:
            lines.append(f"Headline: {candidate['headline']}")
        if candidate["summary"]:
            lines.append(f"Summary: {candidate['summary']}")
        if source["experience"]:
            lines.append("Experience:")
            for entry in source["experience"]:
                heading = " at ".join(
                    part for part in (entry["title"], entry["company"]) if part
                )
                if entry["dates"]:
                    heading += f" ({entry['dates']})"
                lines.append(f"- {heading}")
                for bullet in entry["bullets"]:
                    lines.append(f"  * {bullet}")
        if source["skills"]:
            lines.append("Skills: " + ", ".join(source["skills"]))

        lines.extend([
            "",
            "TARGET JOB",
            f"Title: {job['title']}",
            f"Company: {job['company'] or '(not provided)'}",
        ])
        if job["required_skills"]:
            lines.append("Required skills: " + ", ".join(job["required_skills"]))
        if job["preferred_skills"]:
            lines.append("Preferred skills: " + ", ".join(job["preferred_skills"]))
        if job["description_excerpt"]:
            lines.extend(["", "Job description excerpt:", job["description_excerpt"]])

        lines.extend([
            "",
            f"Tone: {_TONE_INSTRUCTIONS[tone]}",
            "Write the cover letter now, following every hard rule.",
        ])
        return "\n".join(lines)


def source_character_count(source: dict) -> int:
    """Approximate the amount of text sent, for the UI's privacy summary."""
    return len(json.dumps(source, ensure_ascii=False))
