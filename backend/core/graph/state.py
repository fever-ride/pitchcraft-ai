from dataclasses import dataclass, field
from typing import TypedDict
import time


class PipelineState(TypedDict, total=False):
    # Identity
    client_id: str
    project_id: str
    proposal_id: str

    # Brief
    raw_brief: str
    structured_brief: dict
    brief_confirmed: bool

    # Research + Strategy
    research_result: dict
    research_fetched_at: float
    strategy_insight: dict
    strategy_result: dict
    brand_check_passed: bool

    # Strategy confirmation
    strategy_confirmed: bool
    strategy_feedback: str

    # Resources
    resource_result: dict
    resource_types_needed: list

    # Deck
    deck_structure: list
    structure_confirmed: bool
    slides: list
    slides_confirmed: bool
    narrative_suggestions: list

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
