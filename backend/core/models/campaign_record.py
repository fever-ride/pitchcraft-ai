"""CampaignRecord schema for the Campaign Knowledge Base (Phase 5).

A structured decision record extracted from project recap/case study reports.
Each completed project produces one record. Fields are organized by knowledge
dimension, matching how agents consume them:

  Strategy layer    → Strategy P2
  Communication layer → Strategy P2, Deck Orchestrator
  Media layer       → Media Planning Agent
  Execution layer   → Resource Agent
  Outcome layer     → All agents
"""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator


# --- Enums ---

class CampaignType(str, Enum):
    LAUNCH = "launch"
    BRANDING = "branding"
    CONVERSION = "conversion"
    EVENT = "event"
    CRISIS = "crisis"
    ALWAYS_ON = "always_on"
    OTHER = "other"


class BudgetTier(str, Enum):
    UNDER_100K = "under_100k"
    TIER_100K_500K = "100k_500k"
    TIER_500K_2M = "500k_2m"
    TIER_2M_5M = "2m_5m"
    ABOVE_5M = "above_5m"


class ConfirmationStatus(str, Enum):
    PENDING = "pending_confirmation"
    CONFIRMED = "confirmed"


class Confidence(str, Enum):
    HIGH = "high"
    PARTIAL = "partial"
    LOW = "low"


# --- Sub-models: Strategy Layer ---

class RejectedDirection(BaseModel):
    """A strategic direction that was considered and dropped."""
    direction: str
    reason: str | None = None


class StrategyDecisions(BaseModel):
    """What strategic direction was chosen and why."""
    industry_insight: str | None = None
    audience_insight: str | None = None
    strategy_framework: str | None = None
    big_idea: str | None = None
    big_idea_rationale: str | None = None
    positioning: str | None = None
    rejected_directions: list[RejectedDirection] = Field(default_factory=list)


# --- Sub-models: Communication Layer ---

class ChannelStrategy(BaseModel):
    """Strategy for a single channel within the communication plan."""
    channel: str | None = None
    channel_type: str | None = None  # "social" / "offline" / "pr" / "paid"
    role: str | None = None
    content_direction: str | None = None
    target_audience_segment: str | None = None


class CommunicationPlan(BaseModel):
    """How to reach the audience. Channel mix, phasing, cross-platform logic."""
    channel_mix: list[ChannelStrategy] = Field(default_factory=list)
    phasing_structure: str | None = None  # e.g. "三阶段：预热/引爆/长尾" (vectorized)
    phasing_rhythm: str | None = None  # e.g. "首波引爆后5-7天跟进第二波" (vectorized)
    cross_platform_logic: str | None = None
    content_themes: list[str] = Field(default_factory=list)


# --- Sub-models: Media Layer ---

class TierAllocation(BaseModel):
    """Budget and resource allocation for a single tier."""
    tier: str | None = None
    platform: str | None = None
    count: int | None = None
    budget_allocated: str | None = None
    budget_percentage: float | None = None
    role: str | None = None
    selection_criteria: str | None = None
    budget_missing: bool = False

    @model_validator(mode='after')
    def check_budget_present(self):
        if self.budget_allocated is None and self.budget_percentage is None:
            self.budget_missing = True
        return self


class MediaPlan(BaseModel):
    """What to buy and how much to spend. Only covers paid/purchased resources."""
    total_media_budget: str | None = None
    channel_budget_split: dict[str, str] = Field(default_factory=dict)
    tier_breakdown: list[TierAllocation] = Field(default_factory=list)
    rationale: str | None = None


# --- Sub-models: Execution Layer ---

class ResourceUsed(BaseModel):
    """A specific resource that was used in execution."""
    name: str | None = None
    type: str | None = None
    tier: str | None = None
    platform: str | None = None
    cost: str | None = None
    deliverables: str | None = None


class ExecutionDetail(BaseModel):
    """How the plan was actually carried out."""
    resources_used: list[ResourceUsed] = Field(default_factory=list)
    content_formats: list[str] = Field(default_factory=list)
    vendors_used: list[str] = Field(default_factory=list)
    actual_timeline: list[str] = Field(
        default_factory=list)  # concrete dates, MongoDB only


# --- Sub-models: Outcome Layer ---

class Outcome(BaseModel):
    """What happened. Results, learnings, reusable insights."""
    kpi_results: dict[str, str] = Field(default_factory=dict)
    best_performing_tier: str | None = None
    best_performing_channel: str | None = None
    underperforming_areas: list[str] = Field(default_factory=list)
    lessons_learned: list[str] = Field(default_factory=list)
    reusable_insights: list[str] = Field(default_factory=list)
    overall_rating: int | None = Field(None, ge=1, le=5)


# --- Sub-models: Client Learnings ---

class ClientLearnings(BaseModel):
    """How this client makes decisions. Feeds Brief Analyzer in future projects."""
    decision_style: str | None = None
    client_approved_directions: list[str] = Field(default_factory=list)
    client_rejected_directions: list[str] = Field(default_factory=list)
    kpi_priorities: list[str] = Field(default_factory=list)
    communication_notes: str | None = None


# --- Sub-models: Deck Info ---

class DeckInfo(BaseModel):
    """Structural information about the presentation deck."""
    slide_count: int | None = None
    chapter_structure: list[str] = Field(default_factory=list)
    presentation_style: str | None = None


# --- Meta ---

class CampaignMeta(BaseModel):
    """Fields used for retrieval matching. All indexed for filtering."""
    campaign_type: CampaignType | None = None
    industry: str | None = None
    budget_tier: BudgetTier | None = None
    target_audience_summary: str | None = None
    duration_days: int | None = None
    channels_used: list[str] = Field(default_factory=list)
    client_id: str | None = None


# --- Top-level record ---

class CampaignRecord(BaseModel):
    """Complete structured record of a campaign project.

    Extracted by LLM from recap reports, confirmed by humans, then indexed
    for cross-campaign retrieval. All fields optional because extraction
    may be partial depending on source document completeness.
    """
    id: str | None = Field(None, alias="_id")

    meta: CampaignMeta = Field(default_factory=CampaignMeta)
    strategy_decisions: StrategyDecisions = Field(
        default_factory=StrategyDecisions)
    communication_plan: CommunicationPlan = Field(
        default_factory=CommunicationPlan)
    media_plan: MediaPlan = Field(default_factory=MediaPlan)
    execution: ExecutionDetail = Field(default_factory=ExecutionDetail)
    outcome: Outcome = Field(default_factory=Outcome)
    client_learnings: ClientLearnings = Field(default_factory=ClientLearnings)
    deck_info: DeckInfo = Field(default_factory=DeckInfo)

    # Metadata
    status: ConfirmationStatus = ConfirmationStatus.PENDING
    confidence: Confidence = Confidence.PARTIAL
    source_archive_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None


# --- Extraction sub-schemas (one per LLM call) ---

class ExtractionBackground(BaseModel):
    """First extraction call: project background + strategy decisions."""
    meta: CampaignMeta = Field(default_factory=CampaignMeta)
    strategy_decisions: StrategyDecisions = Field(
        default_factory=StrategyDecisions)
    communication_plan: CommunicationPlan = Field(
        default_factory=CommunicationPlan)
    deck_info: DeckInfo = Field(default_factory=DeckInfo)
    confidence: Confidence = Confidence.PARTIAL


class ExtractionExecution(BaseModel):
    """Second extraction call: media plan + execution details."""
    media_plan: MediaPlan = Field(default_factory=MediaPlan)
    execution: ExecutionDetail = Field(default_factory=ExecutionDetail)
    confidence: Confidence = Confidence.PARTIAL


class ExtractionOutcome(BaseModel):
    """Third extraction call: results, learnings, and client decision patterns."""
    outcome: Outcome = Field(default_factory=Outcome)
    client_learnings: ClientLearnings = Field(default_factory=ClientLearnings)
    confidence: Confidence = Confidence.PARTIAL
