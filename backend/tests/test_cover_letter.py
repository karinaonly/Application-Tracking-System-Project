"""D8: cover-letter source selection, availability, guard, and ownership."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError

from app.cover_letter.schemas import CoverLetterRequest
from app.cover_letter.service import (
    MAX_BULLETS,
    MAX_JD_CHARS,
    MAX_SKILLS,
    CoverLetterService,
)
from app.jobs.models import JobDescription
from app.resume.models import Resume

GOOD_LETTER = """Dear Hiring Manager,

I am applying for the Backend Engineer role at Northwind Labs. I build backend services with Python and PostgreSQL, and I care about clear data models and predictable APIs.

In my current role as a Backend Developer at Contoso Systems, I design and maintain services that support internal teams. I have worked with Docker to package applications, and I have written tests for the endpoints I own. I enjoy the part of the work where a vague requirement becomes a simple, reliable design.

Your posting asks for someone who can work with Python and PostgreSQL while collaborating with other teams. That matches the work I do today. I would bring careful implementation, honest estimates, and a habit of documenting decisions so the next person can pick up the work.

Thank you for your time. I would welcome the chance to discuss how I can help your team.

Sincerely,
Alex Rivera"""


def make_resume(**overrides) -> Resume:
    values = {
        "user_id": uuid4(),
        "filename": "resume.txt",
        "file_path": "/tmp/resume.txt",
        "file_type": "txt",
        "raw_text": "raw resume text",
        "parsed_data": {
            "sections": {
                "contact_parsed": {
                    "name": "Alex Rivera",
                    "title": "Backend Developer",
                    "email": "alex.rivera@example.com",
                    "phone": "+1 555 0100",
                    "location": "Springfield",
                    "linkedin": "https://linkedin.com/in/alex-rivera",
                    "github": "https://github.com/alex-rivera",
                    "portfolio": "https://alex.example.com",
                },
                "summary": {
                    "raw": "Backend developer focused on Python services and PostgreSQL."
                },
                "experience_parsed": [
                    {
                        "title": "Backend Developer",
                        "company": "Contoso Systems",
                        "dates": "2024 - Present",
                        "bullets": [
                            "Built services with Python and PostgreSQL.",
                            "Packaged applications with Docker.",
                        ],
                    }
                ],
                "skills_parsed": ["Python", "PostgreSQL", "Docker"],
            }
        },
    }
    values.update(overrides)
    return Resume(**values)


def make_job(**overrides) -> JobDescription:
    values = {
        "user_id": uuid4(),
        "title": "Backend Engineer",
        "company": "Northwind Labs",
        "raw_text": "We need a backend engineer with Python and PostgreSQL experience. " * 100,
        "extracted_keywords": {
            "required_skills": ["Python", "PostgreSQL"],
            "preferred_skills": ["Docker"],
        },
    }
    values.update(overrides)
    return JobDescription(**values)


class FakeAI:
    provider = "fake"
    model = "fake-model"

    def __init__(self, replies, client=object()):
        self.replies = list(replies)
        self.client = client
        self.calls = []

    def generate_text(self, system_prompt, user_prompt, **kwargs):
        self.calls.append((system_prompt, user_prompt))
        reply = self.replies.pop(0) if self.replies else ("", "no reply queued")
        if isinstance(reply, tuple):
            return reply
        return reply, None


class FakeSession:
    def __init__(self, resumes=(), jobs=()):
        self.resumes = {resume.id: resume for resume in resumes}
        self.jobs = {job.id: job for job in jobs}

    def get(self, model, item_id):
        if model is Resume:
            return self.resumes.get(item_id)
        if model is JobDescription:
            return self.jobs.get(item_id)
        return None


def enabled_settings():
    return SimpleNamespace(ai_rewriting_enabled=True)


def disabled_settings():
    return SimpleNamespace(ai_rewriting_enabled=False)


class SourceSelectionTests(unittest.TestCase):
    def setUp(self):
        self.resume = make_resume()
        self.job = make_job(user_id=self.resume.user_id)
        self.session = FakeSession([self.resume], [self.job])
        self.service = CoverLetterService(self.session, ai=FakeAI([GOOD_LETTER]))

    def test_preview_returns_available_source(self):
        with patch(
            "app.cover_letter.service.get_settings", return_value=enabled_settings()
        ):
            preview = self.service.preview(
                self.resume.id, self.job.id, self.resume.user_id
            )

        self.assertTrue(preview["available"])
        self.assertEqual(preview["reason"], "ready")
        self.assertEqual(preview["source"]["candidate"]["name"], "Alex Rivera")
        self.assertEqual(
            preview["source"]["job"]["title"], "Backend Engineer"
        )
        self.assertEqual(
            preview["source"]["job"]["description_excerpt"][-1:],
            self.job.raw_text[:MAX_JD_CHARS][-1:],
        )

    def test_source_never_includes_contact_details(self):
        with patch(
            "app.cover_letter.service.get_settings", return_value=enabled_settings()
        ):
            preview = self.service.preview(
                self.resume.id, self.job.id, self.resume.user_id
            )

        serialized = json.dumps(preview["source"])
        for secret in (
            "alex.rivera@example.com",
            "+1 555 0100",
            "Springfield",
            "linkedin.com/in/alex-rivera",
            "github.com/alex-rivera",
            "alex.example.com",
        ):
            self.assertNotIn(secret, serialized)

    def test_source_is_capped(self):
        resume = make_resume(
            parsed_data={
                "sections": {
                    "contact_parsed": {"name": "Alex Rivera"},
                    "experience_parsed": [
                        {
                            "title": "Developer",
                            "company": "Contoso",
                            "bullets": [f"Bullet {i}" for i in range(20)],
                        }
                    ],
                    "skills_parsed": [f"Skill {i}" for i in range(40)],
                }
            }
        )
        job = make_job(user_id=resume.user_id, raw_text="x" * 10_000)
        service = CoverLetterService(
            FakeSession([resume], [job]), ai=FakeAI([GOOD_LETTER])
        )

        with patch(
            "app.cover_letter.service.get_settings", return_value=enabled_settings()
        ):
            preview = service.preview(resume.id, job.id, resume.user_id)

        self.assertEqual(len(preview["source"]["skills"]), MAX_SKILLS)
        self.assertEqual(
            sum(len(entry["bullets"]) for entry in preview["source"]["experience"]),
            MAX_BULLETS,
        )
        self.assertEqual(
            len(preview["source"]["job"]["description_excerpt"]), MAX_JD_CHARS
        )
        self.assertEqual(preview["source"]["limits"]["experience_bullets"], MAX_BULLETS)

    def test_server_switch_disables_generation(self):
        with patch(
            "app.cover_letter.service.get_settings", return_value=disabled_settings()
        ):
            preview = self.service.preview(
                self.resume.id, self.job.id, self.resume.user_id
            )
            with self.assertRaises(HTTPException) as raised:
                self.service.generate(
                    self.resume.id, self.job.id, self.resume.user_id
                )

        self.assertFalse(preview["available"])
        self.assertEqual(preview["reason"], "disabled_by_server")
        self.assertEqual(raised.exception.status_code, 503)

    def test_unconfigured_ai_disables_generation(self):
        service = CoverLetterService(
            self.session, ai=FakeAI([GOOD_LETTER], client=None)
        )
        with patch(
            "app.cover_letter.service.get_settings", return_value=enabled_settings()
        ):
            preview = service.preview(self.resume.id, self.job.id, self.resume.user_id)
            with self.assertRaises(HTTPException) as raised:
                service.generate(self.resume.id, self.job.id, self.resume.user_id)

        self.assertFalse(preview["available"])
        self.assertEqual(preview["reason"], "not_configured")
        self.assertEqual(raised.exception.status_code, 503)

    def test_foreign_resume_is_a_404(self):
        with self.assertRaises(HTTPException) as raised:
            self.service.preview(self.resume.id, self.job.id, uuid4())

        self.assertEqual(raised.exception.status_code, 404)

    def test_foreign_job_is_a_404(self):
        # The resume belongs to the caller, but the job belongs to someone else.
        self.job.user_id = uuid4()

        with self.assertRaises(HTTPException) as raised:
            self.service.preview(self.resume.id, self.job.id, self.resume.user_id)

        self.assertEqual(raised.exception.status_code, 404)

    def test_unknown_ids_are_404s(self):
        with self.assertRaises(HTTPException):
            self.service.preview(uuid4(), self.job.id, self.resume.user_id)
        with self.assertRaises(HTTPException):
            self.service.preview(self.resume.id, uuid4(), self.resume.user_id)


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.resume = make_resume()
        self.job = make_job(user_id=self.resume.user_id)
        self.session = FakeSession([self.resume], [self.job])

    def generate(self, ai, tone="professional"):
        service = CoverLetterService(self.session, ai=ai)
        with patch(
            "app.cover_letter.service.get_settings", return_value=enabled_settings()
        ):
            return service.generate(
                self.resume.id, self.job.id, self.resume.user_id, tone=tone
            )

    def test_successful_generation_returns_text_and_source(self):
        ai = FakeAI([GOOD_LETTER])

        result = self.generate(ai)

        self.assertEqual(result["text"], GOOD_LETTER)
        self.assertEqual(result["word_count"], len(GOOD_LETTER.split()))
        self.assertEqual(result["tone"], "professional")
        self.assertEqual(result["guard"]["status"], "passed")
        self.assertFalse(result["guard"]["retried"])
        self.assertEqual(result["provider"], "fake")
        self.assertEqual(result["source"]["candidate"]["name"], "Alex Rivera")
        self.assertEqual(len(ai.calls), 1)

    def test_prompt_contains_facts_but_not_contact_details(self):
        ai = FakeAI([GOOD_LETTER])

        self.generate(ai)

        _, prompt = ai.calls[0]
        self.assertIn("Alex Rivera", prompt)
        self.assertIn("Python", prompt)
        self.assertIn("Backend Engineer", prompt)
        self.assertNotIn("alex.rivera@example.com", prompt)
        self.assertNotIn("+1 555 0100", prompt)

    def test_placeholder_triggers_one_retry(self):
        ai = FakeAI([GOOD_LETTER.replace("Northwind Labs", "[Company]"), GOOD_LETTER])

        result = self.generate(ai)

        self.assertEqual(len(ai.calls), 2)
        self.assertTrue(result["guard"]["retried"])
        self.assertEqual(result["guard"]["status"], "passed")
        self.assertIn("previous draft was rejected", ai.calls[1][1])

    def test_guard_flags_after_the_retry_instead_of_silently_passing(self):
        invented = GOOD_LETTER.replace(
            "I build backend services", "I build Kubernetes clusters and"
        )
        ai = FakeAI([invented, invented])

        result = self.generate(ai)

        self.assertEqual(len(ai.calls), 2)
        self.assertEqual(result["guard"]["status"], "flagged")
        self.assertTrue(result["guard"]["retried"])
        self.assertTrue(result["guard"]["reasons"])
        self.assertIn("Kubernetes", " ".join(result["guard"]["reasons"]))

    def test_ai_error_is_a_502(self):
        ai = FakeAI([(None, "provider timed out")])

        with self.assertRaises(HTTPException) as raised:
            self.generate(ai)

        self.assertEqual(raised.exception.status_code, 502)
        self.assertIn("provider timed out", raised.exception.detail)

    def test_empty_response_is_a_502(self):
        with self.assertRaises(HTTPException) as raised:
            self.generate(FakeAI([""]))

        self.assertEqual(raised.exception.status_code, 502)

    def test_short_response_is_a_502(self):
        with self.assertRaises(HTTPException) as raised:
            self.generate(FakeAI(["Dear Hiring Manager, thank you."]))

        self.assertEqual(raised.exception.status_code, 502)

    def test_fenced_markdown_is_stripped(self):
        result = self.generate(FakeAI([f"```markdown\n{GOOD_LETTER}\n```"]))

        self.assertFalse(result["text"].startswith("```"))
        self.assertTrue(result["text"].startswith("Dear Hiring Manager"))


class SchemaTests(unittest.TestCase):
    def test_unknown_tone_is_rejected(self):
        with self.assertRaises(ValidationError):
            CoverLetterRequest(resume_id=uuid4(), job_id=uuid4(), tone="dramatic")

    def test_default_tone_is_professional(self):
        request = CoverLetterRequest(resume_id=uuid4(), job_id=uuid4())

        self.assertEqual(request.tone, "professional")


if __name__ == "__main__":
    unittest.main()
