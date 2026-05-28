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


_VERIFICATION_PROMPT = {
    "zh": """判断这批历史案例对当前项目的参考价值。

当前需求：
{query}

检索到的历史案例：
{campaigns_summary}

判断标准：
- sufficient：案例与当前项目在行业、campaign类型、预算档位、目标受众中至少3项高度匹配，可直接参考
- partial：有2项匹配，有参考价值但存在明显差异，参考时需注意局限
- insufficient：匹配度低，强行参考可能导致误导，不建议使用

reason控制在一句话内。""",
    "en": """Judge whether these historical campaigns are relevant enough to inform the current project.

Current query:
{query}

Retrieved campaigns:
{campaigns_summary}

Criteria:
- sufficient: campaigns match on at least 3 of — industry, campaign type, budget tier, target audience. Safe to reference directly.
- partial: 2 dimensions match. Some reference value but notable differences exist. Use with caution.
- insufficient: low match across dimensions. Using these as reference risks misleading the output.

Keep reason to one sentence.""",
}


def _summarise_results(results: list[CampaignRetrievalResult]) -> str:
    lines = []
    for i, r in enumerate(results, 1):
        meta = r.meta
        parts = [
            meta.get("industry", "—"),
            meta.get("campaign_type", "—"),
            meta.get("budget_tier", "—"),
            meta.get("target_audience_summary", "—"),
        ]
        lines.append(f"{i}. {' | '.join(parts)}")
    return "\n".join(lines)


async def verify_retrieval_sufficiency(
    query: str,
    results: list[CampaignRetrievalResult],
) -> SufficiencyCheck:
    """Ask LLM whether retrieved campaigns are relevant enough to use."""
    lang = detect_language(query)
    prompt = _VERIFICATION_PROMPT[lang].format(
        query=query,
        campaigns_summary=_summarise_results(results),
    )
    return await invoke_llm_structured(
        [SystemMessage(content=prompt)],
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

        results.append(CampaignRetrievalResult(
            record_id=record_id,
            matched_propositions=[p[0] for p in props_sorted],
            modules=modules,
            meta=doc.get("meta", {}),
            top_score=props_sorted[0][1] if props_sorted else 0.0,
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

        header = f"[Historical Campaign: {meta_str}]" if meta_str else "[Historical Campaign]"
        sections = [header]

        if r.sufficiency_note:
            sections.append(f"  [参考局限: {r.sufficiency_note}]")

        for module_name, module_data in r.modules.items():
            module_text = json.dumps(module_data, ensure_ascii=False, default=str)
            sections.append(f"  {module_name}: {module_text}")

        parts.append("\n".join(sections))

    return "\n\n---\n\n".join(parts)
