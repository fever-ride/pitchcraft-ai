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
    "zh": """你是知识提取专家。将这条campaign record拆解成原子命题（atomic propositions），供未来项目检索参考。

规则：
1. 每条命题必须自包含——不依赖上下文即可理解
2. 每条命题必须以此固定前缀开头（不得修改）：{meta_prefix}
3. 不要用代词（"该项目"、"这个campaign"），展开为具体描述
4. 每条命题聚焦一个具体决策、数据点或经验——不要生成关于文档结构本身的命题（如"本文档共X页"）
5. 数字和具体信息保留原始值
6. 生成10-18条命题，覆盖所有有实质内容的字段

**以下四类信息是高频遗漏，必须优先覆盖：**

A. 渠道战略定位：写出每个核心平台在整体传播中的角色，而非只记录投放数量。
   ❌ "在小红书投放25位KOL+10位素人"
   ✅ "以小红书为主要种草阵地，KOL+素人双轨布局，辅以抖音做爆发扩散"

B. KPI比较性结论：若record中有目标值、达成率或超出预期的表述，必须写出相对结论，不能只写绝对数字。
   ❌ "全平台总曝光1.05亿+"
   ✅ "全平台总曝光1.05亿+，核心KPI达成率超出预期目标30%以上"

C. 跨字段效率洞察：至少生成2-3条综合多个字段的推导命题，覆盖不同字段组合（如渠道策略×预算效率、KPI结果×内容形式、受众洞察×平台角色）。
   例1："KOC以10%预算占比贡献60%互动量，验证了低成本素人种草策略的高效性"
   例2："以小红书为主要种草阵地结合抖音爆发扩散，双平台组合最终实现全渠道曝光超额完成目标"
   例3："针对25-35岁都市女性的内容策略与高互动率数据印证了受众洞察的准确性"

D. 双视角表述：对涉及业务目标的命题，同时覆盖营销执行视角和业务结果视角，确保包含"用户增长""转化率""ROI""节点营销""本地生活""电商"等业务词汇（如适用）。
   ❌ "通过KOL投放触达目标人群"
   ✅ "通过KOL矩阵投放触达目标人群，实现品牌awareness提升和新客转化增长"

不要生成空泛的命题（如"项目取得了不错的效果"），每条必须包含具体信息。""",
    "en": """You are a knowledge extraction expert. Decompose this campaign record into atomic propositions for future project retrieval.

Rules:
1. Each proposition must be self-contained — understandable without external context
2. Each proposition MUST start with this exact prefix (do not modify): {meta_prefix}
3. No pronouns ("the campaign", "this project") — expand to specific descriptions
4. Each proposition focuses on one specific decision, data point, or learning — do NOT generate propositions about the document structure itself (e.g. "this document has X pages")
5. Keep original numbers and specific information intact
6. Generate 10-18 propositions covering all fields with substantive content

**The following four are frequently missed — prioritise covering them:**

A. Channel strategic role: state each platform's role in the overall communication architecture, not just how many influencers were placed.
   ❌ "Placed 25 KOLs on Xiaohongshu"
   ✅ "Used Xiaohongshu as the primary seeding channel via KOL + nano-influencer dual-track, with Douyin for reach amplification"

B. Comparative KPI: if the record contains target values, achievement rates, or exceeded-expectation language, state the relative outcome — not just the absolute number.
   ❌ "Total reach 105M+"
   ✅ "Total reach 105M+; core KPIs exceeded target by 30%+"

C. Cross-field efficiency insight: generate at least 2-3 propositions that synthesise across different field combinations to reveal ROI or strategic effectiveness (e.g. channel strategy × budget efficiency, KPI outcome × content format, audience insight × platform role).
   e.g. 1: "KOC tier drove 60% of total engagement at only 10% of budget, validating the low-cost seeding approach"
   e.g. 2: "Xiaohongshu-first seeding combined with Douyin amplification enabled the dual-platform strategy to exceed total reach targets"
   e.g. 3: "Content strategy targeting 25–35 urban women was validated by above-benchmark engagement rates"

D. Dual-perspective phrasing: for propositions involving business objectives, cover both the marketing-execution perspective and the business-result perspective, ensuring vocabulary like "user growth", "conversion rate", "ROI", "promotional node", "O2O", "e-commerce" appears where applicable.
   ❌ "KOL placements reached the target audience"
   ✅ "KOL matrix placements reached the target audience, driving brand awareness uplift and new customer conversion growth"

Do not generate vague propositions (e.g. "the project achieved good results"). Each must contain specific information.""",
}


def _build_meta_prefix(record: dict) -> str:
    """Build [brand | industry | subtype | budget | audience | scenario] prefix from record meta.

    Brand name is placed first to differentiate same-category records in embedding space
    (e.g. COSTA vs 雀巢 are both FMCG new launches — without brand name their proposition
    embeddings cluster too close and one displaces the other in top-K retrieval).
    """
    meta = record.get("meta", {})
    parts = []
    # Brand name first — differentiates same-category records
    if meta.get("client_name"):
        parts.append(meta["client_name"])
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


async def extract_propositions(
    record: dict,
    target_count: int | None = None,
) -> list[str]:
    """Extract atomic propositions from a confirmed CampaignRecord dict.

    Args:
        record: confirmed CampaignRecord dict
        target_count: if set, overrides the default "8-15" instruction with
                      "exactly N" — used by eval sweeps only, not production.
    """
    record_text = _record_to_text(record)
    if not record_text.strip():
        return []

    lang = detect_language(record_text)
    prefix = _build_meta_prefix(record)

    if target_count is not None:
        count_instr = {
            "zh": f"恰好生成 {target_count} 条命题",
            "en": f"Generate exactly {target_count} propositions",
        }[lang]
    else:
        count_instr = {
            "zh": "生成10-18条命题，覆盖所有有实质内容的字段",
            "en": "Generate 10-18 propositions covering all fields with substantive content",
        }[lang]

    # Patch rule 6 of the prompt with the resolved count instruction
    base_prompt = PROPOSITION_PROMPT[lang].format(meta_prefix=prefix)
    prompt = base_prompt.replace(
        "生成10-18条命题，覆盖所有有实质内容的字段" if lang == "zh"
        else "Generate 10-18 propositions covering all fields with substantive content",
        count_instr,
    )

    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=record_text),
    ]

    try:
        result = await invoke_llm_structured(
            messages, output_schema=PropositionList, temperature=0, max_tokens=5000
        )
    except Exception as _e:
        # Structured output can raise ValidationError (e.g. list returned as string)
        # instead of returning empty — treat as empty and fall through to Fallback A
        logger.warning(f"invoke_llm_structured raised ({type(_e).__name__}): {_e}; falling back to JSON-text mode")
        result = PropositionList(propositions=[])

    # Fallback A: structured output returned empty — retry with explicit JSON text prompt
    # (happens when with_structured_output tool_calling silently fails for some records,
    #  typically due to very long meta prefixes causing tool_call response issues)
    if not result.propositions:
        import json as _json
        import re as _re
        from backend.core.agents.llm import get_llm
        json_hint = (
            "\n\n**输出格式：只返回一个JSON对象，不要包含任何其他文字，格式为：{\"propositions\": [\"命题1\", \"命题2\", ...]}"
            if lang == "zh"
            else '\n\n**Output format: return ONLY a JSON object, no other text: {"propositions": ["prop1", "prop2", ...]}'
        )
        fallback_messages = [
            SystemMessage(content=prompt + json_hint),
            HumanMessage(content=record_text),
        ]
        try:
            raw_llm = get_llm(temperature=0, max_tokens=5000)
            raw_result = await raw_llm.ainvoke(fallback_messages)
            raw_text = raw_result.content.strip()
            # Strip markdown code fences (handles ```json, ```JSON, ``` variants)
            raw_text = _re.sub(r"^```[a-zA-Z]*\s*\n?", "", raw_text)
            raw_text = _re.sub(r"\n?```\s*$", "", raw_text).strip()
            data = _json.loads(raw_text)
            parsed = data.get("propositions", [])
            if parsed:
                logger.info(f"Used JSON-text fallback for proposition extraction ({len(parsed)} props)")
                return parsed
        except Exception as e:
            logger.warning(f"JSON-text fallback also failed: {e}")

    # Fallback B: generate minimal propositions from structured fields
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
                "campaign_type": meta.get("campaign_type") or "",
                "campaign_subtype": meta.get("campaign_subtype") or "",
                "campaign_scenario": meta.get("campaign_scenario") or "",
                "industry": meta.get("industry") or "",
                "budget_tier": meta.get("budget_tier") or "",
                "record_type": record.get("record_type") or "campaign",
                "pitch_outcome": record.get("pitch_outcome") or "unknown",
            },
        })

    for i in range(0, len(vectors), UPSERT_BATCH):
        batch = vectors[i: i + UPSERT_BATCH]
        index.upsert(vectors=batch, namespace=namespace)

    logger.info(f"Indexed {len(propositions)} propositions for record {record_id}")
    return len(propositions)
