from fastapi import APIRouter, UploadFile, File, Depends, Response
from sqlmodel import Session, select
from uuid import UUID

from app.config.database import get_session
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.resume.models import Resume, ResumeAnalysis
from app.resume.service import ResumeService

router = APIRouter()

@router.get("/")
def list_resumes(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    resumes = session.exec(
        select(Resume).where(Resume.user_id == user.id).order_by(Resume.created_at.desc())
    ).all()
    result = []
    for resume in resumes:
        latest = session.exec(
            select(ResumeAnalysis)
            .where(ResumeAnalysis.resume_id == resume.id)
            .order_by(ResumeAnalysis.created_at.desc())
        ).first()
        result.append({
            "id": resume.id,
            "filename": resume.filename,
            "file_type": resume.file_type,
            "created_at": resume.created_at,
            "latest_analysis": latest,
        })
    return result

@router.post("/upload", status_code=201)
def upload_resume(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    service = ResumeService(session)
    res = service.upload(file, user.id)
    return {"id": res.id, "filename": res.filename, "status": "parsed"}

@router.post("/{resume_id}/analyze")
def analyze_resume(
    resume_id: UUID,
    job_id: UUID | None = None,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    service = ResumeService(session)
    return service.analyze(resume_id, user.id, job_id)

@router.get("/{resume_id}/export")
def export_resume(
    resume_id: UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    service = ResumeService(session)
    data = service.export_docx(resume_id, user.id)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=ATS_Optimized_Resume.docx"}
    )
