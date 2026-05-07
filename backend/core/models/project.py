from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ProjectStatus(str, Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class Project(BaseModel):
    id: str | None = Field(None, alias="_id")
    client_id: str
    assigned_accounts: list[str] = []
    name: str
    status: ProjectStatus = ProjectStatus.DRAFT
    custom_deck_structure: list[dict] | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
