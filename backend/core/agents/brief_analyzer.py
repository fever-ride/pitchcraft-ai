"""Brief Analyzer: parse natural language brief into structured fields and identify gaps."""
from langchain_core.messages import HumanMessage, SystemMessage

from backend.core.agents.llm import invoke_llm_structured
from backend.core.agents.schemas import BriefAnalysis
from backend.core.graph.state import RequestBudget
from backend.core.language.detector import detect_language

SYSTEM_PROMPT = {
    "zh": "你是资深公关营销策略师。把客户brief解析为结构化字段，并找出需要澄清的信息。",
    "en": "You are a senior PR and marketing strategist. Parse the client brief into structured fields and identify information gaps.",
}


async def analyze_brief(raw_brief: str, budget: RequestBudget | None = None) -> BriefAnalysis:
    lang = detect_language(raw_brief)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT[lang]),
        HumanMessage(content=raw_brief),
    ]

    return await invoke_llm_structured(
        messages, output_schema=BriefAnalysis, budget=budget, temperature=0, max_tokens=2048
    )
