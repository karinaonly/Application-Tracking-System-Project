from fastapi import APIRouter, UploadFile, File, Depends, Response, HTTPException
from sqlmodel import Session, select
from uuid import UUID

from app.config.database import get_session
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.resume.models import Resume, ResumeAnalysis, ResumeVersion
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
            # D3: tailored versions stored for this resume (newest first)
            "versions": [
                {
                    "id": v.id,
                    "job_id": v.job_id,
                    "label": v.label,
                    "applied_rewrites_count": len(v.applied_rewrites),
                    "created_at": v.created_at,
                }
                for v in session.exec(
                    select(ResumeVersion)
                    .where(ResumeVersion.resume_id == resume.id)
                    .order_by(ResumeVersion.created_at.desc())
                ).all()
            ],
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
    analysis_id: UUID | None = None,
    # A4: opt-in only — the export keeps the resume's own title unless the
    # user explicitly asks to match the attached job's title.
    match_title: bool = False,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    service = ResumeService(session)
    data = service.export_docx(resume_id, user.id, analysis_id, match_title=match_title)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=ATS_Optimized_Resume.docx"}
    )

@router.post("/{resume_id}/analyses/{analysis_id}/confirm-keywords")
def confirm_keywords(
    resume_id: UUID,
    analysis_id: UUID,
    body: dict,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    # A3: the user confirms which missing keywords they actually have;
    # only these are injected into the exported resume's Skills section.
    keywords = body.get("keywords")
    if not isinstance(keywords, list):
        raise HTTPException(status_code=400, detail="keywords must be a list")
    service = ResumeService(session)
    confirmed, soft_skipped = service.confirm_keywords(
        resume_id, analysis_id, user.id, keywords
    )
    return {"confirmed_keywords": confirmed, "soft_skipped": soft_skipped}

@router.post("/{resume_id}/versions", status_code=201)
def create_version(
    resume_id: UUID,
    body: dict,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    analysis_id = body.get("analysis_id")
    if not analysis_id:
        raise HTTPException(status_code=400, detail="analysis_id is required")
    service = ResumeService(session)
    version = service.create_version(resume_id, user.id, UUID(str(analysis_id)))
    return {
        "id": version.id,
        "resume_id": version.resume_id,
        "job_id": version.job_id,
        "label": version.label,
        "applied_rewrites_count": len(version.applied_rewrites),
        "created_at": version.created_at,
    }

@router.get("/{resume_id}/versions")
def list_versions(
    resume_id: UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    service = ResumeService(session)
    return [
        {
            "id": v.id,
            "resume_id": v.resume_id,
            "job_id": v.job_id,
            "label": v.label,
            "applied_rewrites_count": len(v.applied_rewrites),
            "created_at": v.created_at,
        }
        for v in service.list_versions(resume_id, user.id)
    ]

@router.get("/{resume_id}/versions/{version_id}/export")
def export_version(
    resume_id: UUID,
    version_id: UUID,
    # A4: same opt-in rule as the direct export endpoint.
    match_title: bool = False,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    service = ResumeService(session)
    data, filename = service.export_version_docx(
        resume_id, version_id, user.id, match_title=match_title
    )
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.delete("/{resume_id}/versions/{version_id}", status_code=204)
def delete_version(
    resume_id: UUID,
    version_id: UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    service = ResumeService(session)
    service.delete_version(resume_id, version_id, user.id)
    return Response(status_code=204)
