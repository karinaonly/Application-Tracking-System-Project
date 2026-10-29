"""D7: application tracker rules.

Kept out of the router so the date/status behavior can be tested directly.
"""

from datetime import datetime, timezone

from app.jobs.models import JobDescription

APPLICATION_STATUSES = ("saved", "applied", "interview", "offer", "rejected")

UNSET = object()


def update_application(
    job: JobDescription,
    *,
    status: str | None = None,
    applied_at: datetime | None | object = UNSET,
    notes: str | None = None,
    now: datetime | None = None,
) -> JobDescription:
    """Apply a partial tracker update to ``job``.

    * Moving to any non-"saved" status without a date records "now" -- the
      moment the user says the application moved, never a guessed past date.
    * ``applied_at=None`` clears the date; omitting it leaves the date alone.
    * Notes are trimmed, and an empty string clears them.
    """
    if status is not None:
        job.application_status = status
        if (
            status != "saved"
            and job.applied_at is None
            and applied_at is UNSET
        ):
            job.applied_at = now or datetime.now(timezone.utc)

    if applied_at is not UNSET:
        job.applied_at = applied_at  # type: ignore[assignment]

    if notes is not None:
        job.notes = notes.strip()

    return job
