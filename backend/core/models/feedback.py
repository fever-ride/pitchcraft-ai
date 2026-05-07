from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class FeedbackTarget(str, Enum):
    STRATEGY = "strategy"
    STRUCTURE = "structure"
    SLIDE = "slide"
    RESOURCE = "resource"
    OVERALL = "overall"


class Feedback(BaseModel):
    id: str | None = Field(None, alias="_id")
    proposal_id: str
    client_id: str
    project_id: str | None = None
    target: FeedbackTarget = FeedbackTarget.OVERALL
    content: str
    approved_directions: list[str] = []
    rejected_directions: list[str] = []
    tags: list[str] = []
    rerun_triggered: bool = False
    rerun_from_node: str | None = None
    embedded: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


# Maps feedback target to the suggested rerun node
RERUN_SUGGESTIONS: dict[FeedbackTarget, str] = {
    FeedbackTarget.STRATEGY: "strategy_phase2",
    FeedbackTarget.STRUCTURE: "deck_orchestrator",
    FeedbackTarget.SLIDE: "slide_content",
    FeedbackTarget.RESOURCE: "resource_agent",
    FeedbackTarget.OVERALL: "strategy_phase2",
}
