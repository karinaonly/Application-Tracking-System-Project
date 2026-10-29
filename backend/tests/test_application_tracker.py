"""D7: application tracker status, dates, notes, and ownership."""

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError

from app.jobs.models import JobDescription
from app.jobs.router import update_job_application
from app.jobs.schemas import JobApplicationUpdate
from app.jobs.tracker import update_application

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


def make_job(**overrides) -> JobDescription:
    values = {
        "user_id": uuid4(),
        "title": "Backend Engineer",
        "raw_text": "Build APIs.",
    }
    values.update(overrides)
    return JobDescription(**values)


class TrackerRulesTests(unittest.TestCase):
    def test_new_job_defaults_to_saved_without_a_date(self):
        job = make_job()

        self.assertEqual(job.application_status, "saved")
        self.assertIsNone(job.applied_at)
        self.assertEqual(job.notes, "")

    def test_marking_applied_records_now(self):
        job = make_job()

        update_application(job, status="applied", now=NOW)

        self.assertEqual(job.application_status, "applied")
        self.assertEqual(job.applied_at, NOW)

    def test_existing_applied_date_is_not_overwritten(self):
        original = datetime(2026, 10, 1, tzinfo=timezone.utc)
        job = make_job(application_status="applied", applied_at=original)

        update_application(job, status="interview", now=NOW)

        self.assertEqual(job.application_status, "interview")
        self.assertEqual(job.applied_at, original)

    def test_explicit_date_is_used_instead_of_now(self):
        job = make_job()
        backfilled = datetime(2026, 9, 15, tzinfo=timezone.utc)

        update_application(job, status="applied", applied_at=backfilled, now=NOW)

        self.assertEqual(job.applied_at, backfilled)

    def test_explicit_none_clears_the_date(self):
        job = make_job(application_status="applied", applied_at=NOW)

        update_application(job, applied_at=None)

        self.assertIsNone(job.applied_at)

    def test_omitting_the_date_leaves_it_alone(self):
        job = make_job(application_status="applied", applied_at=NOW)

        update_application(job, status="offer")

        self.assertEqual(job.applied_at, NOW)

    def test_notes_are_trimmed_and_cleared(self):
        job = make_job()

        update_application(job, notes="  Recruiter call Friday  ")
        self.assertEqual(job.notes, "Recruiter call Friday")

        update_application(job, notes="   ")
        self.assertEqual(job.notes, "")

    def test_moving_back_to_saved_keeps_the_applied_date(self):
        job = make_job(application_status="applied", applied_at=NOW)

        update_application(job, status="saved")

        self.assertEqual(job.application_status, "saved")
        self.assertEqual(job.applied_at, NOW)

    def test_unknown_status_is_rejected_by_the_schema(self):
        with self.assertRaises(ValidationError):
            JobApplicationUpdate(status="ghosted")

    def test_notes_have_a_length_limit(self):
        with self.assertRaises(ValidationError):
            JobApplicationUpdate(notes="x" * 5001)


class FakeSession:
    def __init__(self, job):
        self.job = job
        self.committed = False

    def get(self, model, job_id):
        return self.job if self.job is not None and self.job.id == job_id else None

    def add(self, job):
        self.job = job

    def commit(self):
        self.committed = True

    def refresh(self, job):
        pass


class TrackerEndpointTests(unittest.TestCase):
    def test_owner_can_update_status_notes_and_date(self):
        job = make_job()
        session = FakeSession(job)
        user = SimpleNamespace(id=job.user_id)

        result = update_job_application(
            job.id,
            JobApplicationUpdate(
                status="interview",
                applied_at=NOW,
                notes="Panel scheduled",
            ),
            user=user,
            session=session,
        )

        self.assertIs(result, job)
        self.assertTrue(session.committed)
        self.assertEqual(job.application_status, "interview")
        self.assertEqual(job.applied_at, NOW)
        self.assertEqual(job.notes, "Panel scheduled")

    def test_omitted_date_is_not_cleared_through_the_endpoint(self):
        job = make_job(application_status="applied", applied_at=NOW)
        session = FakeSession(job)
        user = SimpleNamespace(id=job.user_id)

        update_job_application(
            job.id,
            JobApplicationUpdate(status="offer"),
            user=user,
            session=session,
        )

        self.assertEqual(job.applied_at, NOW)

    def test_explicit_null_clears_the_date_through_the_endpoint(self):
        job = make_job(application_status="applied", applied_at=NOW)
        session = FakeSession(job)
        user = SimpleNamespace(id=job.user_id)

        update_job_application(
            job.id,
            JobApplicationUpdate(applied_at=None),
            user=user,
            session=session,
        )

        self.assertIsNone(job.applied_at)

    def test_foreign_job_is_a_404(self):
        job = make_job()
        session = FakeSession(job)
        other_user = SimpleNamespace(id=uuid4())

        with self.assertRaises(HTTPException) as raised:
            update_job_application(
                job.id,
                JobApplicationUpdate(status="applied"),
                user=other_user,
                session=session,
            )

        self.assertEqual(raised.exception.status_code, 404)
        self.assertFalse(session.committed)
        self.assertEqual(job.application_status, "saved")

    def test_unknown_job_is_a_404(self):
        session = FakeSession(None)
        user = SimpleNamespace(id=uuid4())

        with self.assertRaises(HTTPException) as raised:
            update_job_application(
                uuid4(),
                JobApplicationUpdate(status="applied"),
                user=user,
                session=session,
            )

        self.assertEqual(raised.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
