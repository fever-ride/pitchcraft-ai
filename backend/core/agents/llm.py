"""Shared LLM invocation with model routing and budget tracking.

Model routing allows per-agent model selection for cost optimization.
Heavy creative tasks use Sonnet; simple extraction/classification uses Haiku or GPT-4o-mini.
"""
from typing import TypeVar

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from pydantic import BaseModel

from backend.core.config import settings
from backend.core.graph.state import RequestBudget

T = TypeVar("T", bound=BaseModel)


# --- Model Registry ---

MODEL_CONFIGS = {
    "sonnet": {
        "provider": "anthropic",
        "model": "claude-sonnet-4-6-20250514",
    },
    "haiku": {
        "provider": "anthropic",
        "model": "claude-haiku-4-5-20251001",
    },
    "gpt-4o-mini": {
        "provider": "openai",
        "model": "gpt-4o-mini",
    },
}

AGENT_MODEL_MAP: dict[str, str] = {
    "brief_analyzer": "haiku",
    "research": "sonnet",
    "strategy_phase1": "sonnet",
    "strategy_phase2": "sonnet",
    "media_planner": "sonnet",
    "resource": "haiku",
    "brand_check": "haiku",
    "deck_orchestrator": "sonnet",
    "slide_content": "sonnet",
    "narrative": "haiku",
    "campaign_extract": "haiku",
    "proposition_index": "haiku",
    "backfill": "haiku",
}

DEFAULT_MODEL = "sonnet"


def get_llm(
    temperature: float = 0,
    max_tokens: int = 2048,
    agent_name: str | None = None,
    model_override: str | None = None,
) -> BaseChatModel:
    """Get LLM instance with model routing.

    Priority: model_override > agent_name lookup > DEFAULT_MODEL
    """
    model_key = model_override or AGENT_MODEL_MAP.get(agent_name or "", DEFAULT_MODEL)
    config = MODEL_CONFIGS.get(model_key, MODEL_CONFIGS[DEFAULT_MODEL])

    if config["provider"] == "openai":
        return _get_openai_llm(config["model"], temperature, max_tokens)
    return _get_anthropic_llm(config["model"], temperature, max_tokens)


def _get_anthropic_llm(model: str, temperature: float, max_tokens: int) -> ChatAnthropic:
    return ChatAnthropic(
        model=model,
        api_key=settings.anthropic_api_key,
        max_tokens=max_tokens,
        temperature=temperature,
    )


def _get_openai_llm(model: str, temperature: float, max_tokens: int) -> BaseChatModel:
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=model,
        api_key=settings.openai_api_key,
        max_tokens=max_tokens,
        temperature=temperature,
    )


async def invoke_llm(
    messages: list[BaseMessage],
    budget: RequestBudget | None = None,
    temperature: float = 0,
    max_tokens: int = 2048,
    agent_name: str | None = None,
    model_override: str | None = None,
) -> str:
    """Invoke LLM with budget enforcement. Returns the text content."""
    if budget:
        budget.use_llm_call()

    llm = get_llm(
        temperature=temperature,
        max_tokens=max_tokens,
        agent_name=agent_name,
        model_override=model_override,
    )
    response = await llm.ainvoke(messages)
    text = response.content

    if isinstance(text, list):
        text = text[0].get("text", "") if text else ""

    return text.strip()


async def invoke_llm_structured(
    messages: list[BaseMessage],
    output_schema: type[T],
    budget: RequestBudget | None = None,
    temperature: float = 0,
    max_tokens: int = 2048,
    agent_name: str | None = None,
    model_override: str | None = None,
) -> T:
    """Invoke LLM with tool_use-based structured output. Returns a validated Pydantic model instance."""
    if budget:
        budget.use_llm_call()

    llm = get_llm(
        temperature=temperature,
        max_tokens=max_tokens,
        agent_name=agent_name,
        model_override=model_override,
    )
    structured_llm = llm.with_structured_output(output_schema)
    return await structured_llm.ainvoke(messages)


def strip_code_block(text: str) -> str:
    """Remove markdown code block wrapper if present."""
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()
