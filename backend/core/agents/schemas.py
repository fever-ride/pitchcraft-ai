"""Pydantic output schemas for all agents. Used with invoke_llm_structured() for tool_use-based structured output."""
from pydantic import BaseModel, Field


# --- Brief Analyzer ---

class StructuredBrief(BaseModel):
    client_name: str = Field(default="not provided", description="Brand/client name or 'not provided'")
    theme: str = Field(default="not provided", description="Campaign theme/direction or 'not provided'")
    audience: str = Field(default="not provided", description="Target audience or 'not provided'")
    channels: list[str] = Field(default_factory=list, description="Channel list")
    budget: str = Field(default="not provided", description="Budget range or 'not provided'")
    timeline: str = Field(default="not provided", description="Timeline or 'not provided'")
    objective: str = Field(default="not provided", description="Campaign objective or 'not provided'")


class BriefAnalysis(BaseModel):
    structured_brief: StructuredBrief
    missing_fields: list[str] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list)


# --- Research Agent ---

class CompetitorSocialPresence(BaseModel):
    platforms: list[str] = Field(default_factory=list)
    content_style: str = ""
    engagement_level: str = Field(default="medium", description="high/medium/low")
    notable_campaigns: list[str] = Field(default_factory=list)


class Competitor(BaseModel):
    name: str
    positioning: str = ""
    recent_activity: str = ""
    social_presence: CompetitorSocialPresence = Field(default_factory=CompetitorSocialPresence)


class ContentTrend(BaseModel):
    trend: str
    platforms: list[str] = Field(default_factory=list)
    relevance: str = ""


class ResearchResult(BaseModel):
    competitors: list[Competitor] = Field(default_factory=list)
    market_trends: list[str] = Field(default_factory=list)
    content_trends: list[ContentTrend] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    internal_references: list[str] = Field(default_factory=list)
    recommended_approach: str = ""


# --- Strategy Phase 1 ---

class StrategyPhase1Result(BaseModel):
    audience_insight: str = Field(description="Key audience insight")
    brand_direction: str = Field(description="Recommended brand direction")
    tone_keywords: list[str] = Field(default_factory=list, description="Brand tone keywords")
    competitive_gap: str = Field(default="", description="Identified competitive gap")
    initial_angles: list[str] = Field(default_factory=list, description="Potential creative angles")


# --- Strategy Phase 2 ---

class Channel(BaseModel):
    name: str
    role: str = Field(default="", description="Channel's role in the campaign")
    priority: str = Field(default="medium", description="high/medium/low")


class TimelinePhase(BaseModel):
    phase: str
    duration: str = ""
    activities: list[str] = Field(default_factory=list)


class StrategyPhase2Result(BaseModel):
    big_idea: str = Field(description="Core creative concept")
    big_idea_rationale: str = Field(default="", description="Why this idea works")
    channels: list[Channel] = Field(default_factory=list)
    resource_types: list[str] = Field(default_factory=list, description="Required resource types: kol, media, vendor, placement")
    budget_allocation: dict[str, str] = Field(default_factory=dict)
    kpis: list[str] = Field(default_factory=list)
    timeline_phases: list[TimelinePhase] = Field(default_factory=list)


# --- Brand Check ---

class BrandCheckResult(BaseModel):
    passed: bool = Field(description="Whether strategy aligns with brand guidelines")
    issues: list[str] = Field(default_factory=list)


# --- Resource Agent ---

class RecommendedResource(BaseModel):
    name: str
    type: str = Field(description="kol/koc/media/vendor/placement")
    reason: str = ""
    estimated_cost: str = ""
    tags: list[str] = Field(default_factory=list)


class ResourceResult(BaseModel):
    recommended_resources: list[RecommendedResource] = Field(default_factory=list)
    channel_allocation: dict[str, str] = Field(default_factory=dict)
    missing_resources: list[str] = Field(default_factory=list)


# --- Deck Orchestrator ---

class SlideStructure(BaseModel):
    slide_index: int
    title: str
    type: str = Field(description="cover/overview/insight/strategy/channel/budget/timeline/kpi/appendix")
    key_points: list[str] = Field(default_factory=list)


class DeckStructureResult(BaseModel):
    slides: list[SlideStructure]


# --- Slide Content ---

class SlideContent(BaseModel):
    title: str
    body: str = Field(description="1-2 sentence summary")
    bullets: list[str] = Field(default_factory=list)


# --- Narrative Check ---

class NarrativeIssue(BaseModel):
    page: int
    issue: str


class NarrativeResult(BaseModel):
    issues: list[NarrativeIssue] = Field(default_factory=list)
