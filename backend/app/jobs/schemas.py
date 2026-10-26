from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional

class JobCreate(BaseModel):
    title: str
    company: Optional[str] = None
    raw_text: str
    url: Optional[str] = None

class JobFromUrl(BaseModel):
    url: str

class JobResponse(BaseModel):
    id: UUID
    title: str
    company: Optional[str] = None
    raw_text: str
    url: Optional[str] = None
    created_at: datetime
