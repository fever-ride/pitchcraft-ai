"""Archive Agent: extract structured knowledge from project recap/case study reports."""
from langchain_core.messages import HumanMessage, SystemMessage

from backend.core.agents.llm import invoke_llm_structured
from backend.core.agents.schemas import ArchiveExtraction
from backend.core.language.detector import detect_language

SYSTEM_PROMPT = {
    "zh": (
        "你是资深项目分析师。从结案报告中提取结构化信息，包括：策略经验、受众洞察、"
        "各资源表现数据、内容风格总结。只提取报告中明确提到的信息，不要推测。"
    ),
    "en": (
        "You are a senior project analyst. Extract structured information from project recap reports, "
        "including: strategy learnings, audience insights, resource performance data, and content style "
        "observations. Only extract information explicitly stated in the report — do not speculate."
    ),
}


async def extract_archive(report_text: str) -> ArchiveExtraction:
    """Extract structured knowledge from a recap report text."""
    lang = detect_language(report_text)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT[lang]),
        HumanMessage(content=report_text[:8000]),
    ]

    return await invoke_llm_structured(
        messages, output_schema=ArchiveExtraction, temperature=0, max_tokens=3000
    )
