"""Campaign Knowledge Base: proposition extraction + vectorization (Phase 5.5).

After human confirmation, a CampaignRecord is decomposed into atomic propositions,
each embedded with a meta prefix for contextual retrieval, then upserted to Pinecone.
"""
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from backend.core.agents.llm import invoke_llm_structured
from backend.core.language.detector import detect_language
from backend.core.rag.embedder import embed_texts
from backend.core.rag.indexer import _get_index

logger = logging.getLogger(__name__)

UPSERT_BATCH = 100

# --- Proposition extraction schema ---

class PropositionList(BaseModel):
    propositions: list[str] = Field(default_factory=list)


# --- Prompts ---

PROPOSITION_PROMPT = {
    "zh": """你是知识提取专家。将这条campaign record拆解成原子命题（atomic propositions）。

规则：
1. 每条命题必须自包含——不依赖上下文即可理解
2. 每条命题必须以此固定前缀开头（不得修改）：{meta_prefix}
3. 不要用代词（"该项目"、"这个campaign"），展开为具体描述
4. 每条命题聚焦一个具体决策、数据点或经验——不要生成关于文档结构本身的命题（如"本文档共X页"）
5. 数字和具体信息保留原始值
6. 生成8-15条命题，覆盖所有有实质内容的字段

不要生成空泛的命题（如"项目取得了不错的效果"），每条必须包含具体信息。""",
    "en": """You are a knowledge extraction expert. Decompose this campaign record into atomic propositions.

Rules:
1. Each proposition must be self-contained — understandable without external context
2. Each proposition MUST start with this exact prefix (do not modify): {meta_prefix}
3. No pronouns ("the campaign", "this project") — expand to specific descriptions
4. Each proposition focuses on one specific decision, data point, or learning — do NOT generate propositions about the document structure itself (e.g. "this document has X pages")
5. Keep original numbers and specific information intact
6. Generate 8-15 propositions covering all fields with substantive content

Do not generate vague propositions (e.g. "the project achieved good results"). Each must contain specific information.""",
}


def _build_meta_prefix(record: dict) -> str:
    """Build [industry | subtype | budget | audience | scenario] prefix from record meta."""
    meta = record.get("meta", {})
    parts = []
    if meta.get("industry"):
        parts.append(meta["industry"])
    # Use campaign_subtype for semantic richness; fall back to campaign_type enum value
    type_label = meta.get("campaign_subtype") or meta.get("campaign_type") or ""
    if type_label:
        parts.append(str(type_label))
    budget = meta.get("budget_tier")
    parts.append(budget if budget else "预算未知")
    if meta.get("target_audience_summary"):
        parts.append(meta["target_audience_summary"])
    if meta.get("campaign_scenario"):
        parts.append(meta["campaign_scenario"])
    return f"[{' | '.join(parts)}]" if parts else ""


def _record_to_text(record: dict) -> str:
    """Serialize record fields into readable text for LLM proposition extraction."""
    import json
    sections = []

    meta = record.get("meta", {})
    if any(meta.values()):
        sections.append(f"Meta: {json.dumps(meta, ensure_ascii=False, default=str)}")

    strategy = record.get("strategy_decisions", {})
    if any(v for v in strategy.values() if v):
        sections.append(f"Strategy: {json.dumps(strategy, ensure_ascii=False, default=str)}")

    comms = record.get("communication_plan", {})
    if any(v for v in comms.values() if v):
        sections.append(f"Communication Plan: {json.dumps(comms, ensure_ascii=False, default=str)}")

    media = record.get("media_plan", {})
    if any(v for v in media.values() if v):
        sections.append(f"Media Plan: {json.dumps(media, ensure_ascii=False, default=str)}")

    execution = record.get("execution", {})
    if any(v for v in execution.values() if v):
        sections.append(f"Execution: {json.dumps(execution, ensure_ascii=False, default=str)}")

    outcome = record.get("outcome", {})
    if any(v for v in outcome.values() if v):
        sections.append(f"Outcome: {json.dumps(outcome, ensure_ascii=False, default=str)}")

    client = record.get("client_learnings", {})
    if any(v for v in client.values() if v):
        sections.append(f"Client Learnings: {json.dumps(client, ensure_ascii=False, default=str)}")

    deck = record.get("deck_info", {})
    if any(v for v in deck.values() if v):
        sections.append(f"Deck Info: {json.dumps(deck, ensure_ascii=False, default=str)}")

    return "\n\n".join(sections)


async def extract_propositions(record: dict) -> list[str]:
    """Extract atomic propositions from a confirmed CampaignRecord dict."""
    record_text = _record_to_text(record)
    if not record_text.strip():
        return []

    lang = detect_language(record_text)
    prefix = _build_meta_prefix(record)
    prompt = PROPOSITION_PROMPT[lang].format(meta_prefix=prefix)

    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=record_text),
    ]

    result = await invoke_llm_structured(
        messages, output_schema=PropositionList, temperature=0, max_tokens=3000
    )

    # Fallback: if LLM returns empty, generate basic propositions from meta
    if not result.propositions:
        fallback = []
        strategy = record.get("strategy_decisions", {})
        if strategy.get("big_idea"):
            fallback.append(f"{prefix} Big Idea: {strategy['big_idea']}")
        outcome = record.get("outcome", {})
        for lesson in outcome.get("lessons_learned", []):
            fallback.append(f"{prefix} {lesson}")
        for insight in outcome.get("reusable_insights", []):
            fallback.append(f"{prefix} {insight}")
        return fallback

    return result.propositions


async def index_campaign_propositions(
    record_id: str,
    record: dict,
    org_id: str,
):
    """Extract propositions, embed, and upsert to Pinecone campaign_knowledge namespace.

    Called after human confirmation. Stores propositions in both MongoDB
    (for traceability) and Pinecone (for retrieval).
    """
    from backend.core.database.connection import get_database

    propositions = await extract_propositions(record)
    if not propositions:
        logger.warning(f"No propositions extracted for record {record_id}")
        return 0

    # Store propositions in MongoDB for traceability
    db = await get_database()
    prop_docs = [
        {
            "campaign_record_id": record_id,
            "text": prop,
            "index": i,
        }
        for i, prop in enumerate(propositions)
    ]
    await db["campaign_propositions"].insert_many(prop_docs)

    # Embed and upsert to Pinecone
    embeddings = await embed_texts(propositions)
    namespace = f"campaign_knowledge_{org_id}"

    meta = record.get("meta", {})
    index = _get_index()
    vectors = []
    for i, (prop, emb) in enumerate(zip(propositions, embeddings)):
        vectors.append({
            "id": f"camp_{record_id}_{i}",
            "values": emb,
            "metadata": {
                "campaign_record_id": record_id,
                "text": prop[:1000],
                "campaign_type": meta.get("campaign_type", ""),
                "campaign_subtype": meta.get("campaign_subtype", ""),
                "campaign_scenario": meta.get("campaign_scenario", ""),
                "industry": meta.get("industry", ""),
                "budget_tier": meta.get("budget_tier", ""),
                "record_type": record.get("record_type", "campaign"),
                "pitch_outcome": record.get("pitch_outcome", "unknown"),
            },
        })

    for i in range(0, len(vectors), UPSERT_BATCH):
        batch = vectors[i: i + UPSERT_BATCH]
        index.upsert(vectors=batch, namespace=namespace)

    logger.info(f"Indexed {len(propositions)} propositions for record {record_id}")
    return len(propositions)
