from datetime import datetime

from pydantic import BaseModel, Field


class Proposal(BaseModel):
    id: str | None = Field(None, alias="_id")
    project_id: str
    created_by: str
    version: int = 1
    structured_brief: dict | None = None
    strategy_result: dict | None = None
    deck_structure: list[dict] | None = None
    slides: list[dict] | None = None
    pptx_path: str | None = None
    stage_metrics: dict | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
