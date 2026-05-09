"""Shared LLM invocation with budget tracking."""
from typing import TypeVar

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage
from pydantic import BaseModel

from backend.core.config import settings
from backend.core.graph.state import RequestBudget

T = TypeVar("T", bound=BaseModel)


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


async def invoke_llm_structured(
    messages: list[BaseMessage],
    output_schema: type[T],
    budget: RequestBudget | None = None,
    temperature: float = 0,
    max_tokens: int = 2048,
) -> T:
    """Invoke LLM with tool_use-based structured output. Returns a validated Pydantic model instance.

    Uses LangChain's with_structured_output() which forces the LLM to respond via
    tool_use with the given schema — achieving ~99% format compliance vs ~90% for
    prompt-based JSON extraction.
    """
    if budget:
        budget.use_llm_call()

    llm = get_llm(temperature=temperature, max_tokens=max_tokens)
    structured_llm = llm.with_structured_output(output_schema)
    return await structured_llm.ainvoke(messages)


def strip_code_block(text: str) -> str:
    """Remove markdown code block wrapper if present."""
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()
