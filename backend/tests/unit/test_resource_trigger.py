"""Tests for resource trigger logic — multi-type detection (no external deps)."""
import json

# Inlined from backend.core.agents.resource to avoid import chain
SOCIAL_RESOURCE_TYPES = {"kol", "koc", "influencer", "红人", "达人"}
SOCIAL_CHANNELS = {"小红书", "抖音", "weibo", "instagram", "tiktok", "youtube", "bilibili", "douyin"}
PR_KEYWORDS = {"pr", "media relations", "媒体", "公关", "press", "记者", "发稿", "媒介"}
VENDOR_KEYWORDS = {"event", "活动", "线下", "场地", "拍摄", "制作", "production", "photography", "venue"}
PLACEMENT_KEYWORDS = {"ooh", "户外", "电梯", "cinema", "magazine", "广告位", "投放", "placement", "billboard"}


def _detect_needed_types(strategy: dict) -> list[str]:
    needed = []
    resource_types = [t.lower() for t in strategy.get("resource_types", [])]
    channels = [c.get("name", "").lower() if isinstance(c, dict) else str(c).lower() for c in strategy.get("channels", [])]
    text = json.dumps(strategy, ensure_ascii=False).lower()

    if any(t in SOCIAL_RESOURCE_TYPES for t in resource_types):
        needed.append("kol")
    elif any(ch in SOCIAL_CHANNELS for ch in channels):
        needed.append("kol")
    elif any(kw in text for kw in SOCIAL_RESOURCE_TYPES | SOCIAL_CHANNELS):
        needed.append("kol")

    if "media" in resource_types:
        needed.append("media")
    elif any(kw in text for kw in PR_KEYWORDS):
        needed.append("media")

    if "vendor" in resource_types or "event" in resource_types:
        needed.append("vendor")
    elif any(kw in text for kw in VENDOR_KEYWORDS):
        needed.append("vendor")

    if "placement" in resource_types:
        needed.append("placement")
    elif any(kw in text for kw in PLACEMENT_KEYWORDS):
        needed.append("placement")

    return needed


def _needs_resources(strategy: dict) -> bool:
    return len(_detect_needed_types(strategy)) > 0


# --- KOL/KOC trigger ---

def test_kol_from_resource_types():
    strategy = {"resource_types": ["kol", "media"], "channels": []}
    types = _detect_needed_types(strategy)
    assert "kol" in types


def test_kol_from_channel_name():
    strategy = {"resource_types": [], "channels": [{"name": "小红书", "role": "seeding"}]}
    types = _detect_needed_types(strategy)
    assert "kol" in types


def test_kol_fallback_keyword():
    strategy = {"big_idea": "Partner with top KOL on Instagram"}
    types = _detect_needed_types(strategy)
    assert "kol" in types


# --- Media trigger ---

def test_media_from_resource_types():
    strategy = {"resource_types": ["media"], "channels": []}
    types = _detect_needed_types(strategy)
    assert "media" in types


def test_media_from_pr_keyword():
    strategy = {"big_idea": "公关传播策略", "channels": [{"name": "PR", "role": "credibility"}]}
    types = _detect_needed_types(strategy)
    assert "media" in types


def test_media_from_press_keyword():
    strategy = {"big_idea": "Press coverage campaign for product launch"}
    types = _detect_needed_types(strategy)
    assert "media" in types


# --- Vendor trigger ---

def test_vendor_from_resource_types():
    strategy = {"resource_types": ["event", "kol"], "channels": []}
    types = _detect_needed_types(strategy)
    assert "vendor" in types


def test_vendor_from_keyword():
    strategy = {"big_idea": "线下活动体验营销", "channels": [{"name": "event", "role": "engagement"}]}
    types = _detect_needed_types(strategy)
    assert "vendor" in types


# --- Placement trigger ---

def test_placement_from_resource_types():
    strategy = {"resource_types": ["placement"], "channels": []}
    types = _detect_needed_types(strategy)
    assert "placement" in types


def test_placement_from_keyword():
    strategy = {"big_idea": "OOH billboard campaign in tier-1 cities"}
    types = _detect_needed_types(strategy)
    assert "placement" in types


def test_placement_chinese_keyword():
    strategy = {"big_idea": "电梯广告投放覆盖白领人群"}
    types = _detect_needed_types(strategy)
    assert "placement" in types


# --- Multi-type ---

def test_multiple_types_detected():
    strategy = {
        "big_idea": "Integrated campaign",
        "resource_types": ["kol", "media", "placement"],
        "channels": [{"name": "小红书"}, {"name": "OOH"}],
    }
    types = _detect_needed_types(strategy)
    assert "kol" in types
    assert "media" in types
    assert "placement" in types


# --- No trigger ---

def test_no_resources_pure_digital_ads():
    strategy = {
        "big_idea": "SEM and display ads optimization",
        "resource_types": [],
        "channels": [{"name": "SEM", "role": "conversion"}, {"name": "display", "role": "retarget"}],
    }
    assert _needs_resources(strategy) is False


def test_no_resources_clean_strategy():
    strategy = {"big_idea": "Internal team handles all deliverables in-house"}
    assert _needs_resources(strategy) is False
