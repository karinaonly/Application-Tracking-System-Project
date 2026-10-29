from sqlmodel import SQLModel, Field, JSON, Column
from datetime import datetime, timezone
from uuid import uuid4, UUID

class JobDescription(SQLModel, table=True):
    __tablename__ = "job_descriptions"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    title: str
    company: str | None = Field(default=None)
    raw_text: str
    url: str | None = Field(default=None)
    extracted_keywords: dict = Field(default={}, sa_column=Column(JSON))
    # D7: lightweight application tracker. One status per saved job; no
    # fabricated dates -- applied_at is set only when the user says so (or
    # automatically at the moment they mark it applied).
    application_status: str = Field(default="saved", index=True)
    applied_at: datetime | None = Field(default=None)
    notes: str = Field(default="")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))