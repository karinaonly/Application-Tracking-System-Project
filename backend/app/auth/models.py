from sqlmodel import SQLModel, Field
from datetime import datetime, timezone
from uuid import uuid4, UUID

class User(SQLModel, table=True):
    __tablename__ = "users"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    full_name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))