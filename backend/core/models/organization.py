from datetime import datetime

from pydantic import BaseModel, Field


class Organization(BaseModel):
    id: str | None = Field(None, alias="_id")
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
