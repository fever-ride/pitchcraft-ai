"""Tests for resource trigger logic (no external deps)."""
import json

SOCIAL_RESOURCE_TYPES = {"kol", "koc", "influencer", "红人", "达人"}
SOCIAL_CHANNELS = {"小红书", "抖音", "weibo", "instagram", "tiktok", "youtube", "bilibili", "douyin"}


def _needs_resources(strategy: dict) -> bool:
    """Mirrors backend.core.agents.resource._needs_resources"""
    resource_types = [t.lower() for t in strategy.get("resource_types", [])]
    if any(t in SOCIAL_RESOURCE_TYPES for t in resource_types):
        return True

    channels = [c.get("name", "").lower() if isinstance(c, dict) else str(c).lower() for c in strategy.get("channels", [])]
    if any(ch in SOCIAL_CHANNELS for ch in channels):
        return True

    text = json.dumps(strategy, ensure_ascii=False).lower()
    return any(ch in text for ch in SOCIAL_RESOURCE_TYPES | SOCIAL_CHANNELS)


def test_needs_resources_with_structured_resource_types():
    strategy = {
        "big_idea": "Young energy",
        "channels": [{"name": "OOH", "role": "awareness", "priority": "high"}],
        "resource_types": ["kol", "media"],
    }
    assert _needs_resources(strategy) is True


def test_needs_resources_with_structured_channels():
    strategy = {
        "big_idea": "Social buzz",
        "channels": [{"name": "小红书", "role": "seeding", "priority": "high"}],
        "resource_types": ["media"],
    }
    assert _needs_resources(strategy) is True


def test_no_resources_for_pure_media():
    strategy = {
        "big_idea": "Billboard campaign",
        "channels": [{"name": "OOH", "role": "reach", "priority": "high"}, {"name": "print", "role": "authority", "priority": "medium"}],
        "resource_types": ["media", "event"],
    }
    assert _needs_resources(strategy) is False


def test_needs_resources_chinese_channels():
    strategy = {
        "big_idea": "种草",
        "channels": [{"name": "抖音", "role": "种草", "priority": "high"}],
        "resource_types": ["koc"],
    }
    assert _needs_resources(strategy) is True


def test_fallback_keyword_scan():
    """Even without structured fields, keyword scan catches social references."""
    strategy = {"big_idea": "Partner with top KOL on Instagram for viral content"}
    assert _needs_resources(strategy) is True


def test_no_trigger_clean_strategy():
    strategy = {"big_idea": "Premium print campaign targeting executives"}
    assert _needs_resources(strategy) is False
