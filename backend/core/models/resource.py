from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ResourceType(str, Enum):
    KOL = "kol"
    MEDIA = "media"
    VENDOR = "vendor"
    PLACEMENT = "placement"


class Pricing(BaseModel):
    min: float | None = None
    max: float | None = None
    unit: str | None = None
    currency: str = "USD"


class CollaborationRecord(BaseModel):
    client: str
    project_type: str
    date: str
    performance: str | None = None


class Resource(BaseModel):
    id: str | None = Field(None, alias="_id")
    type: ResourceType
    name: str
    tags: list[str] = []
    pricing: Pricing | None = None
    collaboration_history: list[CollaborationRecord] = []
    pinecone_namespace: str | None = None
    metadata: dict = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)
