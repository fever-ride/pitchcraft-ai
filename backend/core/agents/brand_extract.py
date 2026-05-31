"""Brand profile extraction and prompt formatting utilities."""
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from backend.core.agents.llm import invoke_llm_structured

EXTRACT_SYSTEM = {
    "zh": "你是品牌策略专家，擅长从品牌文档中提取结构化的品牌规范信息。",
    "en": "You are a brand strategy expert skilled at extracting structured brand specification information from brand documents.",
}

EXTRACT_PROMPT = {
    "zh": (
        "从品牌文档中提取关键品牌规范信息，专注于有实质内容的字段，"
        "没有明确信息的字段留空列表或null。\n\n品牌文档：\n{text}"
    ),
    "en": (
        "Extract key brand specification information. Only populate fields with explicit information "
        "from the document. Leave fields empty/null if not stated.\n\nBrand document:\n{text}"
    ),
}


class BrandProfileExtraction(BaseModel):
    brand_name: str | None = None
    positioning: str | None = None
    personality: list[str] = []
    target_audience: str | None = None
    tone_principles: list[str] = []
    forbidden_directions: list[str] = []
    key_messages: list[str] = []
    competitive_position: str | None = None


async def extract_brand_profile(text: str, lang: str) -> dict:
    """Extract BrandProfile fields from brand document text via a single LLM call."""
    lang_key = lang if lang in ("zh", "en") else "en"
    messages = [
        SystemMessage(content=EXTRACT_SYSTEM[lang_key]),
        HumanMessage(content=EXTRACT_PROMPT[lang_key].format(text=text[:8000])),
    ]
    result = await invoke_llm_structured(
        messages,
        output_schema=BrandProfileExtraction,
        agent_name="brand_extract",
        temperature=0,
        max_tokens=2000,
    )
    return result.model_dump()


def format_brand_profile_for_prompt(profile: dict, lang: str) -> str:
    """Format a BrandProfile dict into a text block for injection into agent prompts."""
    brand_name = profile.get("brand_name") or ""
    positioning = profile.get("positioning")
    target_audience = profile.get("target_audience")
    personality: list[str] = profile.get("personality") or []
    tone_principles: list[str] = profile.get("tone_principles") or []
    forbidden_directions: list[str] = profile.get("forbidden_directions") or []
    key_messages: list[str] = profile.get("key_messages") or []
    competitive_position = profile.get("competitive_position")
    # Accumulated from the feedback loop — not set by the AE directly
    approved_directions: list[str] = profile.get("approved_directions") or []
    rejected_directions: list[str] = profile.get("rejected_directions") or []

    has_content = any([
        positioning,
        target_audience,
        personality,
        tone_principles,
        forbidden_directions,
        key_messages,
        competitive_position,
        approved_directions,
        rejected_directions,
    ])
    if not has_content:
        return ""

    lines: list[str] = []
    header = f"[Brand Profile: {brand_name}]" if brand_name else "[Brand Profile]"
    lines.append(header)

    if positioning:
        lines.append(f"Positioning: {positioning}")
    if target_audience:
        lines.append(f"Target Audience: {target_audience}")
    if personality:
        lines.append(f"Personality: {', '.join(personality)}")
    if competitive_position:
        lines.append(f"Competitive Position: {competitive_position}")
    if tone_principles:
        lines.append("Tone Principles:")
        for principle in tone_principles:
            lines.append(f"  - {principle}")
    if forbidden_directions:
        lines.append("Forbidden Directions (from brand spec):")
        for direction in forbidden_directions:
            lines.append(f"  - {direction}")
    if key_messages:
        lines.append("Key Messages:")
        for message in key_messages:
            lines.append(f"  - {message}")
    if approved_directions:
        lines.append("Previously Approved Directions (from client feedback):")
        for direction in approved_directions:
            lines.append(f"  - {direction}")
    if rejected_directions:
        lines.append("Previously Rejected Directions (from client feedback):")
        for direction in rejected_directions:
            lines.append(f"  - {direction}")

    return "\n".join(lines)
