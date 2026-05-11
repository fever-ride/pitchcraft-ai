"""Campaign Knowledge Base retrieval (Phase 5.6).

Two-level retrieval: propositions for matching precision, full structured
modules for agent context. Each agent gets a retrieval profile that controls
what it receives.
"""
from dataclasses import dataclass, field

from backend.core.database.connection import get_database
from backend.core.rag.embedder import embed_query
from backend.core.rag.retriever import _get_index


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


async def retrieve_campaign_knowledge(
    query: str,
    org_id: str,
    profile_name: str,
    metadata_filter: dict | None = None,
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

        for module_name, module_data in r.modules.items():
            module_text = json.dumps(module_data, ensure_ascii=False, default=str)
            sections.append(f"  {module_name}: {module_text}")

        parts.append("\n".join(sections))

    return "\n\n---\n\n".join(parts)
