"""MediaPlan schema for Phase 6 Media Planning Agent.

The Media Planning Agent sits between Strategy P2 and Resource Agent.
It transforms strategy-level channel decisions into a structured tier-level
media matrix that Resource Agent executes against.

Boundary:
  Strategy P2 owns channel-level budget allocation (e.g. "小红书 40%, 抖音 30%")
  Media Planning Agent owns tier-level breakdown within each channel.
"""
from pydantic import BaseModel, Field


class MediaTier(BaseModel):
    """A single tier allocation within the media plan."""
    tier: str  # "top" / "mid" / "tail" / "koc" / "media"
    channel: str  # "小红书" / "抖音" / "PR" / etc.
    role: str  # "awareness" / "amplification" / "ugc" / "credibility"
    count: int  # number of resources to procure
    budget_percentage: float  # percentage of this channel's budget
    budget_absolute: float | None = None  # calculated from Strategy's channel budget
    selection_criteria: str  # drives Resource Agent retrieval query
    platform_rationale: str  # why this tier on this platform gets this allocation


class MediaPlan(BaseModel):
    """Structured media plan output from the Media Planning Agent.

    Does NOT include channel-level budget split (owned by Strategy P2).
    Only contains tier-level breakdown within each channel.
    """
    tiers: list[MediaTier] = Field(default_factory=list)
    strategy_interpretation: str | None = None  # how strategy was translated to media needs
    rationale: str | None = None  # overall plan reasoning
    historical_references: list[str] = Field(default_factory=list)  # campaign records consulted
