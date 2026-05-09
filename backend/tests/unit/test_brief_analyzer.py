"""Tests for Brief Analyzer — schema validation and contract tests."""
import pytest

from backend.core.agents.schemas import BriefAnalysis, StructuredBrief


def test_brief_analysis_full():
    result = BriefAnalysis(
        structured_brief=StructuredBrief(
            client_name="Nike",
            theme="Summer Running Campaign",
            audience="Urban runners 25-35",
            channels=["social media", "OOH"],
            budget="500K USD",
            timeline="June-August 2026",
            objective="Increase brand consideration among young runners",
        ),
        missing_fields=[],
        clarification_questions=[],
    )
    assert result.structured_brief.client_name == "Nike"
    assert result.structured_brief.audience == "Urban runners 25-35"
    assert result.missing_fields == []


def test_brief_analysis_with_missing_fields():
    result = BriefAnalysis(
        structured_brief=StructuredBrief(
            client_name="Adidas",
            theme="not provided",
            audience="not provided",
            channels=[],
            budget="not provided",
            timeline="Q3",
            objective="brand awareness",
        ),
        missing_fields=["theme", "audience", "budget"],
        clarification_questions=[
            "What is the campaign direction?",
            "Who is the target audience?",
            "What is the budget range?",
        ],
    )
    assert len(result.missing_fields) == 3
    assert "theme" in result.missing_fields
    assert len(result.clarification_questions) == 3


def test_structured_brief_defaults():
    brief = StructuredBrief(client_name="Test")
    assert brief.theme == "not provided"
    assert brief.audience == "not provided"
    assert brief.budget == "not provided"
    assert brief.channels == []


def test_brief_analysis_serialization():
    result = BriefAnalysis(
        structured_brief=StructuredBrief(
            client_name="Brand X",
            theme="Launch campaign",
            audience="Gen Z",
            channels=["WeChat", "Douyin"],
        ),
        missing_fields=["budget"],
        clarification_questions=["What is the budget?"],
    )
    data = result.model_dump()
    assert data["structured_brief"]["client_name"] == "Brand X"
    assert data["structured_brief"]["channels"] == ["WeChat", "Douyin"]
    assert data["missing_fields"] == ["budget"]
