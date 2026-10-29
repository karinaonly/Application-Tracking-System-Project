from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.config.database import get_session
from app.cover_letter.schemas import CoverLetterRequest
from app.cover_letter.service import CoverLetterService

router = APIRouter()


@router.get("/preview")
def preview_cover_letter(
    resume_id: UUID,
    job_id: UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """D8: show exactly which resume facts would be sent, before anything is.

    This endpoint never calls the AI provider.
    """
    return CoverLetterService(session).preview(resume_id, job_id, user.id)


@router.post("/")
def generate_cover_letter(
    data: CoverLetterRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """D8: generate a cover letter after an explicit user request."""
    return CoverLetterService(session).generate(
        data.resume_id,
        data.job_id,
        user.id,
        tone=data.tone,
    )
