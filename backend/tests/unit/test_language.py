"""Tests for language detection and prompt routing."""
from backend.core.language.detector import detect_language
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
