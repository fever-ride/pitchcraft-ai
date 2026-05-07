"""Shared LLM invocation with budget tracking."""
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage

from backend.core.config import settings
from backend.core.graph.state import RequestBudget


def get_llm(temperature: float = 0, max_tokens: int = 2048) -> ChatAnthropic:
    return ChatAnthropic(
        model="claude-sonnet-4-6-20250514",
        api_key=settings.anthropic_api_key,
        max_tokens=max_tokens,
        temperature=temperature,
    )


async def invoke_llm(
    messages: list[BaseMessage],
    budget: RequestBudget | None = None,
    temperature: float = 0,
    max_tokens: int = 2048,
) -> str:
    """Invoke LLM with budget enforcement. Returns the text content."""
    if budget:
        budget.use_llm_call()

    llm = get_llm(temperature=temperature, max_tokens=max_tokens)
    response = await llm.ainvoke(messages)
    text = response.content

    if isinstance(text, list):
        text = text[0].get("text", "") if text else ""

    return text.strip()


def strip_code_block(text: str) -> str:
    """Remove markdown code block wrapper if present."""
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()
