"""Tests for language detection and prompt routing."""
from backend.core.language.detector import detect_language, resolve_output_language
from backend.core.language.prompts import (
    BRIEF_ANALYZER_PROMPTS,
    STRATEGY_PHASE1_PROMPTS,
    STRATEGY_PHASE2_PROMPTS,
)


def test_detect_chinese():
    assert detect_language("请帮我分析这个客户需求，提取结构化信息并找出需要澄清的问题") == "zh"


def test_detect_english():
    assert detect_language("Please analyze this client brief and extract the structured information for our campaign") == "en"


def test_detect_mixed_defaults_to_either():
    result = detect_language("这是一个关于品牌传播的项目，目标受众是年轻消费者群体")
    assert result in ("zh", "en")


def test_detect_empty_defaults_to_english():
    assert detect_language("") == "en"


def test_all_prompt_templates_have_both_languages():
    for prompts in [BRIEF_ANALYZER_PROMPTS, STRATEGY_PHASE1_PROMPTS, STRATEGY_PHASE2_PROMPTS]:
        assert "zh" in prompts
        assert "en" in prompts
        assert len(prompts["zh"]) > 0
        assert len(prompts["en"]) > 0


def test_brief_prompts_contain_placeholder():
    assert "{brief}" in BRIEF_ANALYZER_PROMPTS["en"]
    assert "{brief}" in BRIEF_ANALYZER_PROMPTS["zh"]


# --- resolve_output_language tests ---


def test_resolve_explicit_en():
    assert resolve_output_language("en", "中文内容不影响结果") == "en"


def test_resolve_explicit_zh():
    assert resolve_output_language("zh", "English content does not matter") == "zh"


def test_resolve_auto_falls_back_to_detection_chinese():
    assert resolve_output_language("auto", "请帮我分析这个品牌的市场定位和竞争优势，制定一份完整的传播策略方案包含目标受众和渠道建议") == "zh"


def test_resolve_auto_falls_back_to_detection_english():
    assert resolve_output_language("auto", "Please analyze the market positioning for this brand") == "en"


def test_resolve_empty_string_treated_as_auto():
    result = resolve_output_language("", "This is English text for testing purposes")
    assert result == "en"
