from datetime import datetime

from pydantic import BaseModel, Field


class Client(BaseModel):
    id: str | None = Field(None, alias="_id")
    organization_id: str
    lead_account_id: str | None = None
    name: str
    industry: str | None = None
    default_deck_structure: list[dict] | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
