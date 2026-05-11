from dataclasses import dataclass, field
from typing import TypedDict
import time


class PipelineState(TypedDict, total=False):
    # Identity
    client_id: str
    project_id: str
    proposal_id: str
    org_id: str

    # Language
    output_language: str  # "zh" | "en" | "auto" — controls deck/slide output language

    # Brief
    raw_brief: str
    structured_brief: dict  # StructuredBrief fields as dict
    missing_fields: list[str]
    clarification_questions: list[str]
    brief_confirmed: bool

    # Research
    research_result: dict  # Full ResearchResult as dict
    research_fetched_at: float
    market_trends: list[str]
    opportunities: list[str]

    # Strategy Phase 1
    strategy_insight: dict  # Full StrategyPhase1Result as dict
    audience_insight: str
    brand_direction: str

    # Strategy Phase 2
    strategy_result: dict  # Full StrategyPhase2Result as dict
    big_idea: str
    content_tone: str  # e.g. "playful and youthful", "专业权威"
    channels: list[dict]  # list of Channel dicts
    resource_types_needed: list[str]  # Typed: ["kol", "media", "vendor", "placement"]
    kpis: list[str]
    timeline_phases: list[dict]
    budget_allocation: dict

    # Brand check
    brand_check_passed: bool

    # Strategy confirmation
    strategy_confirmed: bool
    strategy_feedback: str

    # Resources
    resource_result: dict  # Full ResourceResult as dict

    # Deck
    deck_structure: list[dict]  # list of SlideStructure dicts
    structure_confirmed: bool
    slides: list[dict]
    slides_confirmed: bool
    narrative_suggestions: list[dict]

    # Output
    pptx_path: str

    # Control
    rerun_from: str
    rerun_refresh_research: bool
    request_budget: "RequestBudget"
    stage_metrics: dict


@dataclass
class RequestBudget:
    max_llm_calls: int = 30
    max_search_calls: int = 10
    max_retry_per_agent: int = 2
    max_total_seconds: int = 300
    current_llm_calls: int = 0
    current_search_calls: int = 0
    start_time: float = field(default_factory=time.time)

    def check(self) -> None:
        if self.current_llm_calls >= self.max_llm_calls:
            raise BudgetExceeded("LLM call limit reached")
        if self.current_search_calls >= self.max_search_calls:
            raise BudgetExceeded("Search call limit reached")
        if time.time() - self.start_time > self.max_total_seconds:
            raise BudgetExceeded("Pipeline timeout")

    def use_llm_call(self):
        self.current_llm_calls += 1
        self.check()

    def use_search_call(self):
        self.current_search_calls += 1
        self.check()


class BudgetExceeded(Exception):
    pass
