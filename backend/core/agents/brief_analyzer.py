"""Brief Analyzer: parse natural language brief into structured fields and identify gaps."""
import json

from langchain_core.messages import HumanMessage, SystemMessage

from backend.core.agents.llm import invoke_llm, strip_code_block
from backend.core.graph.state import RequestBudget
from backend.core.language.detector import detect_language

SYSTEM_PROMPT = {
    "zh": """你是资深公关营销策略师。你的任务是把客户brief解析为结构化字段，并找出需要澄清的信息。

输出严格使用以下JSON格式（不要包含其他文字）：
{
  "structured_brief": {
    "client_name": "品牌名称或'未提供'",
    "theme": "campaign主题/方向或'未提供'",
    "audience": "目标受众或'未提供'",
    "channels": ["渠道列表"],
    "budget": "预算范围或'未提供'",
    "timeline": "时间节点或'未提供'",
    "objective": "campaign目标或'未提供'"
  },
  "missing_fields": ["字段名列表"],
  "clarification_questions": ["需要客户回答的问题"]
}""",

    "en": """You are a senior PR and marketing strategist. Your task is to parse a client brief into structured fields and identify information gaps.

Output strictly in the following JSON format (no other text):
{
  "structured_brief": {
    "client_name": "brand name or 'not provided'",
    "theme": "campaign theme/direction or 'not provided'",
    "audience": "target audience or 'not provided'",
    "channels": ["channel list"],
    "budget": "budget range or 'not provided'",
    "timeline": "timeline or 'not provided'",
    "objective": "campaign objective or 'not provided'"
  },
  "missing_fields": ["list of field names"],
  "clarification_questions": ["questions that need client answers"]
}""",
}


async def analyze_brief(raw_brief: str, budget: RequestBudget | None = None) -> dict:
    lang = detect_language(raw_brief)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT[lang]),
        HumanMessage(content=raw_brief),
    ]

    text = await invoke_llm(messages, budget=budget, temperature=0, max_tokens=2048)
    text = strip_code_block(text)

    result = json.loads(text)
    result["language"] = lang
    return result
