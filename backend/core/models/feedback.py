from datetime import datetime

from pydantic import BaseModel, Field


class Feedback(BaseModel):
    id: str | None = Field(None, alias="_id")
    proposal_id: str
    client_id: str
    content: str
    approved_directions: list[str] = []
    rejected_directions: list[str] = []
    rerun_triggered: bool = False
    rerun_from_node: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
