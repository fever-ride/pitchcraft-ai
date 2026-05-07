from datetime import datetime

from pydantic import BaseModel, Field


class StageMetrics(BaseModel):
    id: str | None = Field(None, alias="_id")
    proposal_id: str
    project_id: str
    client_id: str
    brief_analyzer: dict | None = None
    brand_consistency_check: dict | None = None
    research_agent: dict | None = None
    narrative_agent: dict | None = None
    resource_agent: dict | None = None
    request_budget: dict | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
