"""Deck System: structure orchestration, slide content generation, and narrative check."""
import json

from langchain_core.messages import HumanMessage, SystemMessage

from backend.core.agents.llm import invoke_llm_structured
from backend.core.agents.schemas import DeckStructureResult, NarrativeResult, SlideContent
from backend.core.database.connection import get_database
from backend.core.graph.state import RequestBudget
from backend.core.language.detector import resolve_output_language
from backend.core.rag.campaign_retriever import format_campaign_context, retrieve_campaign_knowledge
from backend.core.rag.retriever import format_results_with_sources, retrieve_for_client

ORCHESTRATOR_SYSTEM = {
    "zh": "你是资深Proposal架构师。根据策略方向设计PPT大纲结构。逻辑清晰，层层递进，先insight后策略后落地。通常12-20页。",
    "en": "You are a senior proposal architect. Design PPT outline structure based on strategy. Clear logic, progressive flow from insight to strategy to execution. Typically 12-20 slides.",
}

SLIDE_CONTENT_SYSTEM = {
    "zh": "你是资深文案。为指定slide生成内容，保持品牌调性一致。",
    "en": "You are a senior copywriter. Generate content for the specified slide while maintaining consistent brand tone.",
}

NARRATIVE_SYSTEM = {
    "zh": "你是Proposal审稿人。检查slide序列的叙事连贯性，找出逻辑跳跃或重复冗余。",
    "en": "You are a proposal editor. Check slide sequence for narrative coherence, identify logic jumps or redundancies.",
}


async def _lookup_deck_structure(client_id: str, project_id: str | None) -> list[dict] | None:
    """Three-tier lookup: project -> client -> None (fall through to LLM generation)."""
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
    big_idea: str,
    channels: list[dict],
    kpis: list[str],
    brief: dict,
    client_id: str,
    project_id: str | None = None,
    budget: RequestBudget | None = None,
    output_language: str = "auto",
    org_id: str | None = None,
) -> list[dict]:
    """Generate deck structure from specific strategy fields. Uses saved structure if available."""
    saved = await _lookup_deck_structure(client_id, project_id)
    if saved:
        return saved

    lang = resolve_output_language(output_language, big_idea)

    campaign_context = ""
    if org_id:
        campaign_results = await retrieve_campaign_knowledge(
            query=f"{big_idea} deck structure proposal",
            org_id=org_id,
            profile_name="deck_reference",
        )
        campaign_context = format_campaign_context(campaign_results, max_records=2)

    # Truncate channel roles to keep prompt concise — detailed roles are for media planner, not deck structure
    def _channel_summary(c) -> str:
        if isinstance(c, dict):
            name = c.get("name", "")
            role = c.get("role", "")
            return f"{name}（{role[:60]}）" if role else name
        return str(c)

    channel_summaries = [_channel_summary(c) for c in channels]
    # Truncate KPIs to first 60 chars each to avoid blowing context
    kpi_summaries = [k[:60] for k in kpis]
    user_msg = (
        f"Big Idea: {big_idea}\n"
        f"Channels: {', '.join(channel_summaries)}\n"
        f"KPIs: {', '.join(kpi_summaries)}\n\n"
        f"Brief:\n{json.dumps(brief, ensure_ascii=False)}"
    )
    if campaign_context:
        user_msg += f"\n\nHistorical deck references (for structure inspiration, not constraints):\n{campaign_context}"
    messages = [
        SystemMessage(content=ORCHESTRATOR_SYSTEM[lang]),
        HumanMessage(content=user_msg),
    ]

    result = await invoke_llm_structured(
        messages, output_schema=DeckStructureResult, budget=budget, temperature=0.3, max_tokens=6000
    )
    return [s.model_dump() for s in result.slides]


async def generate_slide_content(
    slide: dict,
    big_idea: str,
    brand_direction: str,
    client_id: str,
    project_id: str | None = None,
    budget: RequestBudget | None = None,
    output_language: str = "auto",
    revision_feedback: str | None = None,
) -> SlideContent:
    """Generate content for a single slide using only the fields it needs."""
    lang = resolve_output_language(output_language, big_idea)

    brand_results = await retrieve_for_client(
        "brand tone voice style guidelines", client_id, project_id, top_k=3
    )
    brand_tone = format_results_with_sources(brand_results) or "No brand tone reference available."

    user_msg = (
        f"Slide: {json.dumps(slide, ensure_ascii=False)}\n"
        f"Big Idea: {big_idea}\n"
        f"Brand Direction: {brand_direction}\n"
        f"Brand Tone Reference:\n{brand_tone[:1000]}"
    )
    if revision_feedback:
        user_msg += f"\n\nRevision required. Previous version was flagged with this feedback:\n{revision_feedback}\nPlease address this feedback in the new version."
    messages = [
        SystemMessage(content=SLIDE_CONTENT_SYSTEM[lang]),
        HumanMessage(content=user_msg),
    ]

    return await invoke_llm_structured(
        messages, output_schema=SlideContent, budget=budget, temperature=0.4, max_tokens=1024
    )


async def run_narrative_check(
    slides: list[dict],
    budget: RequestBudget | None = None,
    output_language: str = "auto",
) -> list[dict]:
    """Non-blocking narrative coherence check. Returns suggestion list."""
    lang = resolve_output_language(output_language, json.dumps(slides, ensure_ascii=False))
    slides_text = json.dumps(slides, ensure_ascii=False)[:4000]

    user_msg = f"Slides:\n{slides_text}"
    messages = [
        SystemMessage(content=NARRATIVE_SYSTEM[lang]),
        HumanMessage(content=user_msg),
    ]

    result = await invoke_llm_structured(
        messages, output_schema=NarrativeResult, budget=budget, temperature=0, max_tokens=1024
    )
    return [issue.model_dump() for issue in result.issues]
