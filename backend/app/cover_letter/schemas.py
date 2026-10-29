from typing import Literal
from uuid import UUID

from pydantic import BaseModel

CoverLetterTone = Literal["professional", "enthusiastic", "concise"]


class CoverLetterRequest(BaseModel):
    resume_id: UUID
    job_id: UUID
    tone: CoverLetterTone = "professional"
