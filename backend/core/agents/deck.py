"""Deck System: structure orchestration, slide content generation, and narrative check."""
import json

from langchain_core.messages import HumanMessage, SystemMessage

from backend.core.agents.llm import invoke_llm, strip_code_block
from backend.core.config import settings
from backend.core.graph.state import RequestBudget
from backend.core.language.detector import detect_language
from backend.core.rag.retriever import retrieve_for_client
from backend.core.database.connection import get_database

ORCHESTRATOR_PROMPT = {
    "zh": """你是资深Proposal架构师。根据策略方向，设计PPT大纲结构。

输出JSON数组，每个元素代表一个slide：
[
  {"slide_index": 0, "title": "标题", "type": "cover/overview/insight/strategy/channel/budget/timeline/kpi/appendix", "key_points": ["要点"]}
]

要求：逻辑清晰，层层递进，先insight后策略后落地。通常12-20页。""",

    "en": """You are a senior proposal architect. Based on the strategy direction, design the PPT outline structure.

Output a JSON array where each element represents a slide:
[
  {"slide_index": 0, "title": "title", "type": "cover/overview/insight/strategy/channel/budget/timeline/kpi/appendix", "key_points": ["key points"]}
]

Requirements: clear logic, progressive flow from insight to strategy to execution. Typically 12-20 slides.""",
}

SLIDE_CONTENT_PROMPT = {
    "zh": """你是资深文案。为以下slide生成内容。保持品牌调性一致。

Slide信息：{slide}
策略方向：{strategy}
品牌语气参考：{brand_tone}

输出JSON：
{{"title": "页面标题", "body": "正文（1-2句话的概括）", "bullets": ["要点1", "要点2", "要点3"]}}""",

    "en": """You are a senior copywriter. Generate content for the following slide. Maintain consistent brand tone.

Slide info: {slide}
Strategy direction: {strategy}
Brand tone reference: {brand_tone}

Output JSON:
{{"title": "slide title", "body": "body text (1-2 sentence summary)", "bullets": ["point 1", "point 2", "point 3"]}}""",
}

NARRATIVE_PROMPT = {
    "zh": """你是Proposal审稿人。检查以下slide序列的叙事连贯性。

Slides：{slides}

找出叙事不连贯、逻辑跳跃或重复冗余的地方。输出JSON数组：
[{{"page": 页码索引, "issue": "问题描述"}}]

如果没问题输出空数组 []""",

    "en": """You are a proposal editor. Check the following slide sequence for narrative coherence.

Slides: {slides}

Identify narrative gaps, logic jumps, or redundancies. Output a JSON array:
[{{"page": page_index, "issue": "issue description"}}]

If no issues, output empty array []""",
}


async def _lookup_deck_structure(client_id: str, project_id: str | None) -> list[dict] | None:
    """Three-tier lookup: project → client → None (fall through to LLM generation)."""
    db = await get_database()

    if project_id:
        project = await db["projects"].find_one({"_id": project_id})
        if project and project.get("custom_deck_structure"):
            return project["custom_deck_structure"]

    client = await db["clients"].find_one({"_id": client_id})
    if client and client.get("default_deck_structure"):
        return client["default_deck_structure"]

    return None


async def run_deck_orchestrator(
    strategy: dict,
    brief: dict,
    client_id: str,
    project_id: str | None = None,
    budget: RequestBudget | None = None,
) -> list[dict]:
    """Generate deck structure from strategy. Uses saved structure if available."""
    saved = await _lookup_deck_structure(client_id, project_id)
    if saved:
        return saved

    lang = detect_language(json.dumps(strategy, ensure_ascii=False))
    strategy_text = json.dumps(strategy, ensure_ascii=False)[:3000]

    user_msg = f"Strategy:\n{strategy_text}\n\nBrief:\n{json.dumps(brief, ensure_ascii=False)}"
    messages = [
        SystemMessage(content=ORCHESTRATOR_PROMPT[lang]),
        HumanMessage(content=user_msg),
    ]

    text = await invoke_llm(messages, budget=budget, temperature=0.3, max_tokens=3000)
    text = strip_code_block(text)

    return json.loads(text)


async def generate_slide_content(
    slide: dict,
    strategy: dict,
    client_id: str,
    project_id: str | None = None,
    budget: RequestBudget | None = None,
) -> dict:
    """Generate content for a single slide."""
    lang = detect_language(json.dumps(strategy, ensure_ascii=False))

    brand_results = await retrieve_for_client(
        "brand tone voice style guidelines", client_id, project_id, top_k=3
    )
    brand_tone = "\n".join([r.text for r in brand_results]) or "No brand tone reference available."

    prompt = SLIDE_CONTENT_PROMPT[lang].format(
        slide=json.dumps(slide, ensure_ascii=False),
        strategy=json.dumps(strategy, ensure_ascii=False)[:1500],
        brand_tone=brand_tone[:1000],
    )

    text = await invoke_llm(
        [HumanMessage(content=prompt)],
        budget=budget,
        temperature=0.4,
        max_tokens=1024,
    )
    text = strip_code_block(text)

    return json.loads(text)


async def run_narrative_check(
    slides: list[dict],
    budget: RequestBudget | None = None,
) -> list[dict]:
    """Non-blocking narrative coherence check. Returns suggestion list."""
    lang = detect_language(json.dumps(slides, ensure_ascii=False))
    slides_text = json.dumps(slides, ensure_ascii=False)[:4000]

    prompt = NARRATIVE_PROMPT[lang].format(slides=slides_text)

    text = await invoke_llm(
        [HumanMessage(content=prompt)],
        budget=budget,
        temperature=0,
        max_tokens=1024,
    )
    text = strip_code_block(text)

    return json.loads(text)
