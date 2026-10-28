from sqlmodel import SQLModel, Field, JSON, Column
from datetime import datetime, timezone
from uuid import uuid4, UUID

class Resume(SQLModel, table=True):
    __tablename__ = "resumes"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    filename: str
    file_path: str
    file_type: str
    raw_text: str = ""
    parsed_data: dict = Field(default={}, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ResumeAnalysis(SQLModel, table=True):
    __tablename__ = "resume_analyses"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    resume_id: UUID = Field(foreign_key="resumes.id", index=True)
    job_id: UUID | None = Field(default=None, foreign_key="job_descriptions.id")
    overall_score: float = 0.0
    ats_score: float = 0.0
    keyword_score: float = 0.0
    bullet_score: float = 0.0
    report: dict = Field(default={}, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ResumeVersion(SQLModel, table=True):
    """D3: a tailored snapshot of a resume for a specific job.

    Created from an analysis whose AI rewrites are APPLIED into the text and
    sections -- storing the result, not a promise. One version per
    (resume, job) pair; re-saving replaces the previous version for that job.
    """
    __tablename__ = "resume_versions"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    resume_id: UUID = Field(foreign_key="resumes.id", index=True)
    job_id: UUID | None = Field(default=None, foreign_key="job_descriptions.id")
    analysis_id: UUID = Field(foreign_key="resume_analyses.id")
    label: str
    raw_text: str = ""
    parsed_data: dict = Field(default={}, sa_column=Column(JSON))
    # {original_bullet: rewritten_bullet} -- only rewrites that actually changed text
    applied_rewrites: dict = Field(default={}, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))