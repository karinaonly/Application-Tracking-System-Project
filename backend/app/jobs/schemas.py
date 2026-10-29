from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Literal, Optional

# D7: the tracker's fixed vocabulary. Anything else is a 422, not silently
# coerced into "saved".
ApplicationStatus = Literal["saved", "applied", "interview", "offer", "rejected"]

class JobCreate(BaseModel):
    title: str
    company: Optional[str] = None
    raw_text: str
    url: Optional[str] = None

class JobFromUrl(BaseModel):
    url: str

class JobApplicationUpdate(BaseModel):
    """D7: partial tracker update.

    ``applied_at=None`` explicitly clears the date; omitting the field leaves
    it untouched. Pydantic's ``model_fields_set`` distinguishes the two.
    """

    status: Optional[ApplicationStatus] = None
    applied_at: Optional[datetime] = None
    notes: Optional[str] = Field(default=None, max_length=5000)

class JobResponse(BaseModel):
    id: UUID
    title: str
    company: Optional[str] = None
    raw_text: str
    url: Optional[str] = None
    extracted_keywords: dict = {}
    application_status: str = "saved"
    applied_at: Optional[datetime] = None
    notes: str = ""
    created_at: datetime
