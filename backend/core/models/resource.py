from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ResourceType(str, Enum):
    KOL = "kol"
    KOC = "koc"
    MEDIA = "media"
    VENDOR = "vendor"
    PLACEMENT = "placement"


class ResourceStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Pricing(BaseModel):
    min: float | None = None
    max: float | None = None
    unit: str | None = None
    currency: str = "CNY"


class CollaborationRecord(BaseModel):
    client: str = ""
    project_type: str = ""
    date: str = ""
    performance: str | None = None
    performance_summary: str = ""
    metrics: dict[str, str] = {}
    recommendation: str = ""


FRESHNESS_THRESHOLD_DAYS = 180


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
    status: ResourceStatus = ResourceStatus.ACTIVE
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_verified_at: datetime | None = None

    # Profile fields (semantic — used in embedding text for similarity matching)
    categories: list[str] = []
    content_style: str | None = None
    audience_tags: list[str] = []
    past_cpe: str | None = None

    # KOL/KOC specific
    followers: str | None = None
    followers_count: int | None = None
    engagement_rate: str | None = None

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

    @property
    def is_stale(self) -> bool:
        if not self.last_verified_at:
            return True
        age = (datetime.utcnow() - self.last_verified_at).days
        return age > FRESHNESS_THRESHOLD_DAYS

    @property
    def freshness_label(self) -> str:
        if not self.last_verified_at:
            return "never verified"
        age_days = (datetime.utcnow() - self.last_verified_at).days
        if age_days <= 30:
            return "recent"
        if age_days <= FRESHNESS_THRESHOLD_DAYS:
            return f"verified {age_days} days ago"
        months = age_days // 30
        return f"data may be outdated ({months} months since last verification)"


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


def parse_follower_count(raw: str | None) -> int | None:
    """Parse follower string like '500万', '12.5k', '3000' into integer."""
    if not raw:
        return None
    text = raw.strip().lower().replace(",", "")
    try:
        if "万" in text:
            return int(float(text.replace("万", "")) * 10000)
        if "k" in text:
            return int(float(text.replace("k", "")) * 1000)
        if "m" in text:
            return int(float(text.replace("m", "")) * 1000000)
        return int(float(text))
    except (ValueError, TypeError):
        return None
