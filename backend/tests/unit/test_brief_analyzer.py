"""Tests for Brief Analyzer with mocked LLM."""
import json
from unittest.mock import AsyncMock, patch

import pytest

langchain_anthropic = pytest.importorskip("langchain_anthropic")

MOCK_LLM_RESPONSE = json.dumps({
    "structured_brief": {
        "client_name": "Nike",
        "theme": "Summer Running Campaign",
        "audience": "Urban runners 25-35",
        "channels": ["social media", "OOH"],
        "budget": "500K USD",
        "timeline": "June-August 2026",
        "objective": "Increase brand consideration among young runners"
    },
    "missing_fields": [],
    "clarification_questions": []
})


@pytest.mark.asyncio
async def test_analyze_brief_returns_structured_output():
    mock_response = AsyncMock()
    mock_response.content = MOCK_LLM_RESPONSE

    with patch("backend.core.agents.brief_analyzer.ChatAnthropic") as MockLLM:
        instance = MockLLM.return_value
        instance.ainvoke = AsyncMock(return_value=mock_response)

        from backend.core.agents.brief_analyzer import analyze_brief
        result = await analyze_brief("Nike wants a summer running campaign targeting young urban runners with 500K budget")

    assert result["structured_brief"]["client_name"] == "Nike"
    assert result["structured_brief"]["audience"] == "Urban runners 25-35"
    assert result["language"] in ("en", "zh")


@pytest.mark.asyncio
async def test_analyze_brief_detects_missing_fields():
    mock_output = json.dumps({
        "structured_brief": {
            "client_name": "Adidas",
            "theme": "not provided",
            "audience": "not provided",
            "channels": [],
            "budget": "not provided",
            "timeline": "Q3",
            "objective": "brand awareness"
        },
        "missing_fields": ["theme", "audience", "budget"],
        "clarification_questions": [
            "What is the campaign direction?",
            "Who is the target audience?",
            "What is the budget range?"
        ]
    })

    mock_response = AsyncMock()
    mock_response.content = mock_output

    with patch("backend.core.agents.brief_analyzer.ChatAnthropic") as MockLLM:
        instance = MockLLM.return_value
        instance.ainvoke = AsyncMock(return_value=mock_response)

        from backend.core.agents.brief_analyzer import analyze_brief
        result = await analyze_brief("Adidas wants to do something in Q3 for brand awareness")

    assert len(result["missing_fields"]) == 3
    assert "theme" in result["missing_fields"]
    assert len(result["clarification_questions"]) == 3


@pytest.mark.asyncio
async def test_analyze_brief_handles_code_block_wrapper():
    wrapped = f"```json\n{MOCK_LLM_RESPONSE}\n```"

    mock_response = AsyncMock()
    mock_response.content = wrapped

    with patch("backend.core.agents.brief_analyzer.ChatAnthropic") as MockLLM:
        instance = MockLLM.return_value
        instance.ainvoke = AsyncMock(return_value=mock_response)

        from backend.core.agents.brief_analyzer import analyze_brief
        result = await analyze_brief("Nike summer campaign")

    assert result["structured_brief"]["client_name"] == "Nike"
