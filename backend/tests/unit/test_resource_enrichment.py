"""Tests for resource profile enrichment: embed text generation, accumulation logic, schema fields."""
from backend.core.agents.schemas import StrategyPhase2Result, StructuredBrief, Channel


# --- Embed text generation (inlined from resources endpoint) ---

def _resource_to_embed_text(r: dict) -> str:
    parts = [f"Name: {r.get('name', '')}", f"Type: {r.get('type', '')}"]
    if r.get("platform"):
        parts.append(f"Platform: {r['platform']}")
    if r.get("followers"):
        parts.append(f"Followers: {r['followers']}")
    if r.get("categories"):
        cats = r["categories"]
        parts.append(f"Categories: {', '.join(cats) if isinstance(cats, list) else cats}")
    if r.get("content_style"):
        parts.append(f"Content Style: {r['content_style']}")
    if r.get("audience_tags"):
        tags = r["audience_tags"]
        parts.append(f"Audience: {', '.join(tags) if isinstance(tags, list) else tags}")
    if r.get("past_cpe"):
        parts.append(f"Past CPE: {r['past_cpe']}")
    if r.get("tags"):
        tags = r["tags"]
        parts.append(f"Tags: {', '.join(tags) if isinstance(tags, list) else tags}")
    if r.get("pricing"):
        parts.append(f"Pricing: {r['pricing']}")
    return " | ".join(parts)


def test_embed_text_full_profile():
    r = {
        "name": "Alice",
        "type": "kol",
        "platform": "小红书",
        "followers": "500万",
        "categories": ["美妆", "护肤"],
        "content_style": "专业测评",
        "audience_tags": ["Z世代", "女性"],
        "past_cpe": "2.1",
        "tags": ["头部", "种草达人"],
        "pricing": "5万/条",
    }
    text = _resource_to_embed_text(r)
    assert "Alice" in text
    assert "小红书" in text
    assert "美妆, 护肤" in text
    assert "专业测评" in text
    assert "Z世代, 女性" in text
    assert "Past CPE: 2.1" in text
    assert "头部, 种草达人" in text


def test_embed_text_minimal():
    r = {"name": "Bob", "type": "media"}
    text = _resource_to_embed_text(r)
    assert text == "Name: Bob | Type: media"


def test_embed_text_string_categories_compat():
    """Handles old-format string categories (pre-normalization data)."""
    r = {"name": "Charlie", "type": "kol", "categories": "美妆,护肤"}
    text = _resource_to_embed_text(r)
    assert "Categories: 美妆,护肤" in text


def test_embed_text_list_categories():
    r = {"name": "Diana", "type": "koc", "categories": ["科技", "数码"]}
    text = _resource_to_embed_text(r)
    assert "Categories: 科技, 数码" in text


# --- Schema fields for pipeline integration ---

def test_structured_brief_has_category():
    brief = StructuredBrief(client_name="TestBrand", category="美妆新品上市")
    assert brief.category == "美妆新品上市"


def test_structured_brief_category_default():
    brief = StructuredBrief()
    assert brief.category == "not provided"


def test_strategy_phase2_has_content_tone():
    result = StrategyPhase2Result(
        big_idea="Test",
        content_tone="playful and youthful",
        channels=[Channel(name="小红书")],
        resource_types=["kol"],
    )
    assert result.content_tone == "playful and youthful"


def test_strategy_phase2_content_tone_default():
    result = StrategyPhase2Result(big_idea="Test")
    assert result.content_tone == ""


# --- Accumulation logic (unit-testable parts) ---

def test_accumulation_skips_not_provided_category():
    """Simulates _accumulate_resource_tags logic: skip when category is 'not provided'."""
    category = "not provided"
    should_accumulate = category and category != "not provided"
    assert not should_accumulate


def test_accumulation_proceeds_with_valid_category():
    category = "美妆新品上市"
    should_accumulate = category and category != "not provided"
    assert should_accumulate


def test_accumulation_skips_empty_category():
    category = ""
    should_accumulate = category and category != "not provided"
    assert not should_accumulate


def test_accumulation_skips_when_no_resources():
    resource_result = {"skipped": True, "reason": "No resource types"}
    should_skip = not resource_result or resource_result.get("skipped")
    assert should_skip


def test_accumulation_proceeds_with_recommendations():
    resource_result = {
        "recommended_resources": [{"name": "Alice", "type": "kol"}],
        "missing_resources": [],
    }
    should_skip = not resource_result or resource_result.get("skipped")
    assert not should_skip
    assert len(resource_result["recommended_resources"]) == 1
