from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ResourceType(str, Enum):
    KOL = "kol"
    KOC = "koc"
    MEDIA = "media"
    VENDOR = "vendor"
    PLACEMENT = "placement"


class Pricing(BaseModel):
    min: float | None = None
    max: float | None = None
    unit: str | None = None
    currency: str = "CNY"


class CollaborationRecord(BaseModel):
    client: str
    project_type: str
    date: str
    performance: str | None = None


class Resource(BaseModel):
    id: str | None = Field(None, alias="_id")
    client_id: str
    type: ResourceType
    name: str
    platform: str = ""
    tags: list[str] = []
    pricing: Pricing | None = None
    collaboration_history: list[CollaborationRecord] = []
    metadata: dict = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # KOL/KOC specific
    followers: str | None = None
    engagement_rate: str | None = None
    content_style: str | None = None

    # Media specific
    outlet_type: str | None = None  # newspaper, magazine, online, TV
    beat: str | None = None  # tech, lifestyle, finance, etc.
    publish_frequency: str | None = None
    contact: str | None = None

    # Vendor specific
    service_type: str | None = None  # event, photography, production, venue
    region: str | None = None
    capacity: str | None = None

    # Placement specific
    placement_type: str | None = None  # OOH, elevator, cinema, magazine_ad
    location: str | None = None
    audience_reach: str | None = None
    available_formats: list[str] = []


def resource_namespace(resource_type: str, client_id: str) -> str:
    """Resolve Pinecone namespace for a resource type."""
    type_map = {
        "kol": "resource_kol",
        "koc": "resource_kol",  # KOC shares namespace with KOL
        "media": "resource_media",
        "vendor": "resource_vendor",
        "placement": "resource_placement",
    }
    prefix = type_map.get(resource_type, "resource_kol")
    return f"{prefix}_{client_id}"
