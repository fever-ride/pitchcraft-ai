"""Tests for resource agent contract — validates that typed strategy fields flow correctly."""
from backend.core.agents.schemas import StrategyPhase2Result, Channel


def test_strategy_result_provides_resource_types():
    result = StrategyPhase2Result(
        big_idea="Integrated KOL campaign",
        channels=[Channel(name="小红书", role="seeding", priority="high")],
        resource_types=["kol", "media"],
        kpis=["engagement rate > 3%"],
    )
    assert result.resource_types == ["kol", "media"]


def test_strategy_result_empty_resource_types():
    result = StrategyPhase2Result(
        big_idea="Internal-only campaign",
        channels=[Channel(name="SEM", role="conversion")],
        resource_types=[],
    )
    assert result.resource_types == []


def test_strategy_result_all_resource_types():
    result = StrategyPhase2Result(
        big_idea="Full-service launch",
        channels=[
            Channel(name="小红书", role="seeding"),
            Channel(name="PR", role="credibility"),
            Channel(name="OOH", role="awareness"),
        ],
        resource_types=["kol", "media", "vendor", "placement"],
    )
    assert len(result.resource_types) == 4
    assert set(result.resource_types) == {"kol", "media", "vendor", "placement"}


def test_channel_model_defaults():
    ch = Channel(name="WeChat")
    assert ch.role == ""
    assert ch.priority == "medium"


def test_strategy_result_serializes_cleanly():
    result = StrategyPhase2Result(
        big_idea="Test idea",
        channels=[Channel(name="Instagram", role="engagement", priority="high")],
        resource_types=["kol"],
        budget_allocation={"social": "60%", "PR": "40%"},
        kpis=["reach 1M impressions"],
    )
    data = result.model_dump()
    assert data["big_idea"] == "Test idea"
    assert data["channels"][0]["name"] == "Instagram"
    assert data["resource_types"] == ["kol"]
    assert data["budget_allocation"] == {"social": "60%", "PR": "40%"}
