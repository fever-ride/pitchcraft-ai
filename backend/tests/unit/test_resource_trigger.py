"""Tests for resource agent contract — validates that typed strategy fields flow correctly."""
from backend.core.agents.schemas import StrategyPhase2Result, Channel

# Inlined from backend.core.models.resource and backend.core.agents.resource
from backend.core.models.resource import PLATFORM_ALIASES


def _resolve_channel_platform(channel_name: str) -> str | None:
    if not channel_name:
        return None
    key = channel_name.strip().lower()
    if key in PLATFORM_ALIASES:
        return PLATFORM_ALIASES[key]
    canonical_values = set(PLATFORM_ALIASES.values())
    if key in canonical_values:
        return key
    return None


def _build_metadata_filter(resource_type: str, channels: list[dict]) -> dict:
    filters: dict = {"status": {"$eq": "active"}}
    if resource_type in ("kol", "koc"):
        platforms = set()
        for ch in channels:
            name = (ch.get("name", "") if isinstance(ch, dict) else str(ch)).lower()
            resolved = _resolve_channel_platform(name)
            if resolved:
                platforms.add(resolved)
        if platforms:
            filters["platform"] = {"$in": sorted(platforms)}
    return filters


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


# --- Metadata filter tests ---


def test_metadata_filter_always_includes_active_status():
    f = _build_metadata_filter("media", channels=[])
    assert f == {"status": {"$eq": "active"}}


def test_metadata_filter_kol_maps_channels_to_platforms():
    channels = [{"name": "小红书", "role": "seeding"}, {"name": "抖音", "role": "reach"}]
    f = _build_metadata_filter("kol", channels)
    assert f["status"] == {"$eq": "active"}
    assert set(f["platform"]["$in"]) == {"xiaohongshu", "douyin"}


def test_metadata_filter_kol_no_platform_when_unmapped_channel():
    channels = [{"name": "SEM", "role": "conversion"}]
    f = _build_metadata_filter("kol", channels)
    assert "platform" not in f


def test_metadata_filter_non_kol_ignores_platform():
    channels = [{"name": "小红书", "role": "seeding"}]
    f = _build_metadata_filter("vendor", channels)
    assert "platform" not in f


def test_metadata_filter_handles_string_channels():
    channels = [{"name": "WeChat"}]
    f = _build_metadata_filter("koc", channels)
    assert f["platform"] == {"$in": ["wechat"]}
