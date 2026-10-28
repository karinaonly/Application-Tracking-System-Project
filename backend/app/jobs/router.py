from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from uuid import UUID

from app.config.database import get_session
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.jobs.models import JobDescription
from app.jobs.parser import JobParser
from app.jobs.schemas import JobCreate, JobFromUrl, JobResponse
from app.jobs.scraper import scrape_job_url

router = APIRouter()
job_parser = JobParser()

@router.post("/", response_model=JobResponse, status_code=201)
def create_job(data: JobCreate, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    job = JobDescription(
        user_id=user.id,
        title=data.title,
        company=data.company,
        raw_text=data.raw_text,
        url=data.url,
        # D2: parse once on save, store the structured result
        extracted_keywords=job_parser.parse(data.raw_text, data.title),
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job

@router.post("/from-url", response_model=JobResponse)
async def create_from_url(data: JobFromUrl, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    try:
        scraped = await scrape_job_url(data.url)
    except ValueError as exc:
        # E6: SSRF-guarded fetch -- surface the block instead of storing junk
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    job = JobDescription(
        user_id=user.id,
        title=scraped.get("title", "Scraped Job"),
        company=scraped.get("company", ""),
        raw_text=scraped.get("text", ""),
        url=data.url,
        extracted_keywords=job_parser.parse(scraped.get("text", ""), scraped.get("title", "Scraped Job")),
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job

@router.get("/", response_model=list[JobResponse])
def list_jobs(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return session.exec(select(JobDescription).where(JobDescription.user_id == user.id)).all()
