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


class ResourceTier(str, Enum):
    TOP = "top"
    MID = "mid"
    TAIL = "tail"
    KOC = "koc"


class ProductionLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ContentStyle(BaseModel):
    """Multi-dimensional content style for media planning matching."""
    production_level: ProductionLevel | None = None  # high / medium / low
    persona_type: str | None = None  # expert / relatable / aspirational / entertaining
    voice_style: str | None = None  # educational / conversational / emotional / humorous


class AudienceDemographics(BaseModel):
    """Structured audience profile for tier-based retrieval matching."""
    age_range: str | None = None  # e.g. "18-24", "25-35"
    gender_skew: str | None = None  # "female", "male", "balanced"
    city_tier: str | None = None  # "tier_1", "tier_2_3", "all"
    interest_tags: list[str] = Field(default_factory=list)


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


class PlatformEntry(BaseModel):
    name: str                        # e.g. "小红书", "抖音"
    followers_raw: str | None = None # original string e.g. "88万"
    followers_count: int | None = None
    profile_url: str | None = None


FRESHNESS_THRESHOLD_DAYS = 180


class Resource(BaseModel):
    id: str | None = Field(None, alias="_id")
    client_id: str
    type: ResourceType
    name: str
    tags: list[str] = []
    pricing: Pricing | None = None
    collaboration_history: list[CollaborationRecord] = []
    metadata: dict = {}
    status: ResourceStatus = ResourceStatus.ACTIVE
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_verified_at: datetime | None = None

    # Tier classification (for media planning matrix matching)
    tier: ResourceTier | None = None

    # Profile fields (semantic — used in embedding text for similarity matching)
    categories: list[str] = []
    content_style: str | None = None          # freeform fallback (e.g. "活泼种草风")
    content_style_v2: ContentStyle | None = None  # structured: production_level / persona_type / voice_style
    audience_tags: list[str] = []             # flat fallback (e.g. ["年轻女性", "美妆"])
    audience_demographics: AudienceDemographics | None = None  # structured: age_range / gender_skew / city_tier
    past_cpe: str | None = None

    # KOL/KOC specific
    platforms: list[PlatformEntry] = []
    primary_platform: str = ""        # normalize_platform(platforms[0].name) — set at import/create time
    total_followers_count: int | None = None   # sum across all platforms, display only
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


PLATFORM_ALIASES = {
    "小红书": "xiaohongshu",
    "red": "xiaohongshu",
    "抖音": "douyin",
    "tiktok": "douyin",
    "微博": "weibo",
    "微信": "wechat",
    "b站": "bilibili",
    "快手": "kuaishou",
    "instagram": "instagram",
    "youtube": "youtube",
    "twitter": "twitter",
    "x": "twitter",
    "linkedin": "linkedin",
    "facebook": "facebook",
}


def normalize_platform(raw: str) -> str:
    """Normalize platform name to canonical form for consistent Pinecone metadata filtering."""
    if not raw:
        return ""
    return PLATFORM_ALIASES.get(raw.strip().lower(), raw.strip().lower())


def parse_follower_count(raw: str | None) -> int | None:
    """Parse follower string into total integer count.

    Handles single values ('500万', '12.5k', '186000') and multi-platform
    strings ('抖音88万+小红书32万') by extracting all number tokens and summing.
    """
    import re
    if not raw:
        return None
    text = raw.strip().lower().replace(",", "")
    # Extract all number+unit tokens, e.g. ["88万", "32万"] from "抖音88万+小红书32万"
    tokens = re.findall(r'[\d.]+(?:万|k|m)?', text)
    if not tokens:
        return None
    try:
        total = 0
        for token in tokens:
            if "万" in token:
                total += int(float(token.replace("万", "")) * 10000)
            elif "k" in token:
                total += int(float(token.replace("k", "")) * 1000)
            elif "m" in token:
                total += int(float(token.replace("m", "")) * 1000000)
            else:
                total += int(float(token))
        return total if total > 0 else None
    except (ValueError, TypeError):
        return None
