"""Campaign Knowledge Base retrieval (Phase 5.6 + 5.8).

Two-level retrieval: propositions for matching precision, full structured
modules for agent context. Each agent gets a retrieval profile that controls
what it receives.

5.8 Self-verification: after retrieval, an LLM judge evaluates whether the
matched campaigns are actually relevant enough to use. Insufficient matches
are dropped so agents don't blindly consume irrelevant historical data.
"""
import logging
from dataclasses import dataclass, field
from enum import Enum

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from backend.core.agents.llm import invoke_llm_structured
from backend.core.database.connection import get_database
from backend.core.language.detector import detect_language
from backend.core.rag.embedder import embed_query
from backend.core.rag.retriever import _get_index

logger = logging.getLogger(__name__)


# --- Retrieval profiles (per-agent) ---

@dataclass
class RetrievalProfile:
    """Controls what an agent receives from Campaign Knowledge Base."""
    top_k: int = 6
    modules: list[str] = field(default_factory=list)
    score_threshold: float = 0.4


PROFILES: dict[str, RetrievalProfile] = {
    "strategy_reference": RetrievalProfile(
        top_k=6,
        modules=["strategy_decisions", "communication_plan", "outcome"],
    ),
    "media_planning": RetrievalProfile(
        top_k=15,
        modules=["media_plan", "execution", "outcome"],
    ),
    "resource_reference": RetrievalProfile(
        top_k=8,
        modules=["execution", "outcome"],
    ),
    "deck_reference": RetrievalProfile(
        top_k=4,
        modules=["deck_info", "communication_plan"],
    ),
    "brief_reference": RetrievalProfile(
        top_k=4,
        modules=["client_learnings", "meta"],
    ),
}


@dataclass
class CampaignRetrievalResult:
    """A matched campaign with relevant modules extracted."""
    record_id: str
    matched_propositions: list[str]
    modules: dict
    meta: dict
    top_score: float
    sufficiency_note: str = ""  # populated when verdict is "partial"


# --- 5.8 Self-verification ---

class SufficiencyVerdict(str, Enum):
    SUFFICIENT = "sufficient"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"


class SufficiencyCheck(BaseModel):
    verdict: SufficiencyVerdict
    reason: str


_VERIFICATION_SYSTEM = {
    "zh": """你是检索质量评估专家。判断检索到的历史案例对当前查询的实际参考价值。

判断逻辑：
1. 先理解当前查询的核心诉求（问的是策略思路、媒介结构、执行细节，还是预算分配？）
2. 逐维度判断差异是否构成实质性阻碍：
   - 预算档位相差2档以上 → 媒介体量和资源配置根本不同，通常是硬障碍
   - 行业不同但媒介诉求相似 → 渠道结构和KOL策略仍有参考价值
   - campaign类型不同但传播逻辑相同 → 节奏和打法可以迁移
3. 综合判断：
   - sufficient：在当前查询最关键的维度上高度匹配，可直接参考
   - partial：有参考价值，但存在需要注意的重要差异
   - insufficient：核心维度严重不匹配，强行参考会产生误导

reason说明哪个维度是关键决定因素，控制在一句话内。""",
    "en": """You are a retrieval quality evaluator. Judge whether the retrieved historical campaigns offer genuine reference value for the current query.

Reasoning steps:
1. Identify the core need in the query (strategy framing, media structure, execution detail, or budget allocation?)
2. For each dimension, ask whether the mismatch actually blocks usefulness for this specific query:
   - Budget tier gap of 2+ tiers → fundamentally different media scale, usually a hard blocker
   - Different industry but similar media objective → channel structure and KOL strategy still transferable
   - Different campaign type but same communication logic → rhythm and mechanics can migrate
3. Verdict:
   - sufficient: strong match on the dimensions that matter most for this query. Safe to reference directly.
   - partial: reference value exists, but there are important differences to flag.
   - insufficient: critical dimensions are mismatched — using these cases risks misleading the output.

Keep reason to one sentence, naming the dimension that drove the verdict.""",
}

_VERIFICATION_USER = {
    "zh": """当前查询：
{query}

检索到的历史案例：
{campaigns_summary}""",
    "en": """Current query:
{query}

Retrieved campaigns:
{campaigns_summary}""",
}


def _summarise_results(results: list[CampaignRetrievalResult]) -> str:
    lines = []
    for i, r in enumerate(results, 1):
        meta = r.meta
        # Use `or "—"` to handle both missing keys and explicit None values
        # (budget_tier is intentionally None when not stated in the document)
        subtype = str(meta.get("campaign_subtype") or "")
        campaign_type = str(meta.get("campaign_type") or "—")
        # Show subtype alongside type if available (e.g. "branding（奥运营销）")
        type_str = f"{campaign_type}（{subtype}）" if subtype else campaign_type
        parts = [
            str(meta.get("industry") or "—"),
            type_str,
            str(meta.get("budget_tier") or "预算未知"),
            str(meta.get("target_audience_summary") or "—"),
        ]
        lines.append(f"{i}. {' | '.join(parts)}")
    return "\n".join(lines)


async def verify_retrieval_sufficiency(
    query: str,
    results: list[CampaignRetrievalResult],
) -> SufficiencyCheck:
    """Ask LLM whether retrieved campaigns are relevant enough to use."""
    lang = detect_language(query)
    user_content = _VERIFICATION_USER[lang].format(
        query=query,
        campaigns_summary=_summarise_results(results),
    )
    return await invoke_llm_structured(
        [
            SystemMessage(content=_VERIFICATION_SYSTEM[lang]),
            HumanMessage(content=user_content),
        ],
        output_schema=SufficiencyCheck,
        temperature=0,
        max_tokens=200,
    )


async def retrieve_campaign_knowledge(
    query: str,
    org_id: str,
    profile_name: str,
    metadata_filter: dict | None = None,
    verify: bool = True,
) -> list[CampaignRetrievalResult]:
    """Retrieve relevant campaign records using proposition-level matching.

    Args:
        query: semantic search query (typically derived from current brief/strategy)
        org_id: organization ID for namespace scoping
        profile_name: key into PROFILES dict (determines top_k and module whitelist)
        metadata_filter: optional Pinecone filter (campaign_type, industry, budget_tier)

    Returns:
        List of CampaignRetrievalResult with matched propositions + full modules
    """
    profile = PROFILES.get(profile_name, PROFILES["strategy_reference"])
    namespace = f"campaign_knowledge_{org_id}"

    # Step 1: Semantic search on propositions
    query_embedding = await embed_query(query)
    index = _get_index()

    query_params = {
        "vector": query_embedding,
        "namespace": namespace,
        "top_k": profile.top_k,
        "include_metadata": True,
    }
    if metadata_filter:
        query_params["filter"] = metadata_filter

    resp = index.query(**query_params)

    # Step 2: Group by campaign_record_id
    record_matches: dict[str, list[tuple[str, float]]] = {}
    for match in resp.matches:
        if match.score < profile.score_threshold:
            continue
        record_id = match.metadata.get("campaign_record_id", "")
        prop_text = match.metadata.get("text", "")
        if record_id:
            record_matches.setdefault(record_id, []).append((prop_text, match.score))

    if not record_matches:
        return []

    # Step 3: Fetch full records from MongoDB, extract relevant modules
    db = await get_database()
    record_ids = list(record_matches.keys())
    cursor = db["campaign_records"].find({"_id": {"$in": record_ids}})
    docs = {str(doc["_id"]): doc async for doc in cursor}

    # Deduplicate: if the same project has both a proposal and a campaign record,
    # keep the campaign as primary and demote the proposal to strategy-reference only.
    # Key: project_id → preferred record_id (campaign wins over proposal)
    project_primary: dict[str, str] = {}
    project_secondary: dict[str, str] = {}  # proposal demoted by a campaign
    for record_id, doc in docs.items():
        project_id = doc.get("project_id")
        if not project_id:
            continue
        record_type = doc.get("record_type", "campaign")
        if project_id not in project_primary:
            project_primary[project_id] = record_id
        else:
            existing_id = project_primary[project_id]
            existing_type = docs[existing_id].get("record_type", "campaign")
            if record_type == "campaign" and existing_type == "proposal":
                # campaign displaces proposal to secondary
                project_secondary[project_id] = existing_id
                project_primary[project_id] = record_id
            elif record_type == "proposal" and existing_type == "campaign":
                project_secondary[project_id] = record_id

    demoted_ids = set(project_secondary.values())

    results: list[CampaignRetrievalResult] = []
    for record_id, props in record_matches.items():
        doc = docs.get(record_id)
        if not doc:
            continue

        # Extract only the modules this profile needs
        modules = {}
        for module_name in profile.modules:
            if module_name in doc and doc[module_name]:
                modules[module_name] = doc[module_name]

        props_sorted = sorted(props, key=lambda x: x[1], reverse=True)
        record_type = doc.get("record_type", "campaign")
        pitch_outcome = doc.get("pitch_outcome", "unknown")

        note = ""
        if record_id in demoted_ids:
            note = "同一项目已有结案数据，此提案仅供策略思路参考，数字为预估值"
        elif record_type == "proposal" and pitch_outcome == "lost":
            note = "未中标方案，可作为对比参考"

        results.append(CampaignRetrievalResult(
            record_id=record_id,
            matched_propositions=[p[0] for p in props_sorted],
            modules=modules,
            meta=doc.get("meta", {}),
            top_score=props_sorted[0][1] if props_sorted else 0.0,
            sufficiency_note=note,
        ))

    results.sort(key=lambda r: r.top_score, reverse=True)

    if not results or not verify:
        return results

    # 5.8 Self-verification: drop or flag results that aren't relevant enough.
    try:
        check = await verify_retrieval_sufficiency(query, results)
        if check.verdict == SufficiencyVerdict.INSUFFICIENT:
            logger.info(f"Campaign retrieval deemed insufficient: {check.reason}")
            return []
        if check.verdict == SufficiencyVerdict.PARTIAL:
            logger.info(f"Campaign retrieval partial: {check.reason}")
            results[0].sufficiency_note = check.reason
    except Exception as e:
        logger.warning(f"Sufficiency verification failed, returning results unfiltered: {e}")

    return results


def format_campaign_context(
    results: list[CampaignRetrievalResult],
    max_records: int = 3,
) -> str:
    """Format campaign retrieval results into agent-consumable text context.

    Returns a structured text block showing matched campaigns with their
    relevant modules, suitable for injection into an agent's prompt.
    """
    if not results:
        return ""

    import json
    parts = []
    for r in results[:max_records]:
        meta_str = ""
        meta = r.meta
        if meta:
            meta_parts = []
            if meta.get("industry"):
                meta_parts.append(meta["industry"])
            if meta.get("campaign_type"):
                meta_parts.append(meta["campaign_type"])
            if meta.get("budget_tier"):
                meta_parts.append(meta["budget_tier"])
            meta_str = " | ".join(meta_parts)

        record_type = r.meta.get("record_type", "campaign") if r.meta else "campaign"
        pitch_outcome = r.meta.get("pitch_outcome", "unknown") if r.meta else "unknown"

        if record_type == "proposal":
            outcome_label = {"won": "中标", "lost": "未中标"}.get(pitch_outcome, "结果未知")
            type_label = f"历史提案·{outcome_label}"
        else:
            type_label = "历史结案"

        header = f"[{type_label}: {meta_str}]" if meta_str else f"[{type_label}]"
        sections = [header]

        if r.sufficiency_note:
            sections.append(f"  [注意: {r.sufficiency_note}]")

        for module_name, module_data in r.modules.items():
            module_text = json.dumps(module_data, ensure_ascii=False, default=str)
            sections.append(f"  {module_name}: {module_text}")

        parts.append("\n".join(sections))

    return "\n\n---\n\n".join(parts)
