"""Resource Agent: multi-type resource matching with Pinecone metadata filtering."""
from langchain_core.messages import HumanMessage, SystemMessage

from backend.core.agents.llm import invoke_llm_structured
from backend.core.agents.schemas import ResourceResult
from backend.core.database.connection import get_database
from backend.core.database.repositories.resources import ResourceRepository
from backend.core.graph.state import RequestBudget
from backend.core.language.detector import resolve_output_language
from backend.core.models.resource import PLATFORM_ALIASES, ResourceStatus, normalize_platform, resource_namespace
from backend.core.rag.campaign_retriever import format_campaign_context, retrieve_campaign_knowledge
from backend.core.rag.retriever import retrieve

SYSTEM_PROMPT = {
    "zh": "你是资深媒介策划。基于策略方向和资源库检索结果，推荐最适合的资源组合。只推荐资源库中实际存在的资源，不要编造。可用类型：KOL/KOC、Media、Vendor、Placement。",
    "en": "You are a senior media planner. Based on the strategy direction and resource database results, recommend the most suitable resource mix. Only recommend resources that exist in the provided database results — do not invent names. Available types: KOL/KOC, Media, Vendor, Placement.",
}


def _resolve_channel_platform(channel_name: str) -> str | None:
    """Resolve a channel name to canonical platform. Returns None for non-platform channels (e.g. SEM, PR)."""
    if not channel_name:
        return None
    key = channel_name.strip().lower()
    if key in PLATFORM_ALIASES:
        return PLATFORM_ALIASES[key]
    canonical_values = set(PLATFORM_ALIASES.values())
    if key in canonical_values:
        return key
    return None


def _infer_resource_type(tier_label: str, channel_name: str) -> str:
    """Infer resource type from tier label and channel context."""
    tier_lower = tier_label.lower()
    channel_lower = channel_name.lower()
    if tier_lower == "media" or channel_lower in ("pr", "媒体"):
        return "media"
    if tier_lower in ("top", "mid", "tail"):
        return "kol"
    if tier_lower == "koc":
        return "koc"
    return "kol"


def _build_metadata_filter(
    resource_type: str,
    channels: list[dict],
) -> dict:
    """Build Pinecone metadata filter dict for a resource type query.

    Always filters active-only. For KOL/KOC, adds platform filter from channels.
    """
    filters: dict = {"status": {"$eq": "active"}}

    if resource_type in ("kol", "koc"):
        platforms = set()
        for ch in channels:
            name = (ch.get("name", "") if isinstance(ch, dict) else str(ch)).lower()
            resolved = _resolve_channel_platform(name)
            if resolved:
                platforms.add(resolved)
        if platforms:
            filters["platforms"] = {"$in": sorted(platforms)}

    return filters


async def _validate_recommendations(
    result: ResourceResult,
    client_id: str = "",
    org_id: str = "",
) -> ResourceResult:
    """Post-validation: verify recommended resources exist in MongoDB and are active.

    Searches both the shared agency pool and the client-specific pool.
    """
    if not result.recommended_resources:
        return result

    db = await get_database()
    repo = ResourceRepository(db)

    validated = []
    for rec in result.recommended_resources:
        # scope="" → searches shared + client pools
        doc = await repo.find_by_name(org_id=org_id, name=rec.name, client_id=client_id, scope="")
        if doc:
            if doc.get("status", ResourceStatus.ACTIVE.value) == ResourceStatus.INACTIVE.value:
                result.missing_resources.append(f"{rec.name} (inactive)")
                continue
            validated.append(rec)
        else:
            result.missing_resources.append(f"{rec.name} (not found in database)")

    result.recommended_resources = validated
    return result


async def run_resource_agent(
    big_idea: str,
    channels: list[dict],
    resource_types_needed: list[str],
    client_id: str = "",
    content_tone: str = "",
    audience_insight: str = "",
    category: str = "",
    budget: RequestBudget | None = None,
    output_language: str = "auto",
    org_id: str | None = None,
    media_plan: dict | None = None,
) -> ResourceResult | dict:
    """Match resources from DB based on typed strategy fields.

    Queries both the shared agency pool (org_id) and the client-specific pool (client_id).
    Semantic query: big_idea + content_tone + audience_insight + category
    Metadata filter: status=active, platform (for KOL/KOC)
    """
    if not resource_types_needed:
        return {"skipped": True, "reason": "No resource types specified by strategy"}

    lang = resolve_output_language(output_language, big_idea)

    query_parts = [big_idea]
    if content_tone:
        query_parts.append(content_tone)
    if audience_insight:
        query_parts.append(audience_insight)
    if category and category != "not provided":
        query_parts.append(category)
    search_query = " ".join(query_parts)

    def _namespaces_for_type(rtype: str) -> list[str]:
        """Return all Pinecone namespaces to query for a given resource type.

        Searches the shared agency pool (if org_id set) and the client-specific
        pool (if client_id set). Deduplicates in case they map to the same namespace.
        """
        nss = []
        if org_id:
            nss.append(resource_namespace(rtype, org_id, scope="shared"))
        if client_id:
            nss.append(resource_namespace(rtype, client_id, scope="client"))
        # Deduplicate while preserving order
        seen: set[str] = set()
        return [n for n in nss if not (n in seen or seen.add(n))]  # type: ignore[arg-type]

    all_results = []
    if media_plan and media_plan.get("tiers"):
        # Tiered retrieval: per-tier query with tier-specific criteria
        for tier_spec in media_plan["tiers"]:
            tier_query = tier_spec.get("selection_criteria", search_query)
            tier_label = tier_spec.get("tier", "")
            channel_name = tier_spec.get("channel", "")
            rtype = _infer_resource_type(tier_label, channel_name)
            namespaces = _namespaces_for_type(rtype)
            if not namespaces:
                continue
            meta_filter = _build_metadata_filter(rtype, channels)
            if tier_label:
                meta_filter["tier"] = {"$eq": tier_label}
            results = await retrieve(
                query=tier_query,
                namespaces=namespaces,
                top_k=tier_spec.get("count", 5) + 3,
                score_threshold=0.25,
                metadata_filter=meta_filter,
            )
            if results:
                all_results.extend(results)
    else:
        # Fallback: generic retrieval per resource type (no media plan)
        for rtype in resource_types_needed:
            namespaces = _namespaces_for_type(rtype)
            if not namespaces:
                continue
            meta_filter = _build_metadata_filter(rtype, channels)
            results = await retrieve(
                query=search_query,
                namespaces=namespaces,
                top_k=8,
                score_threshold=0.3,
                metadata_filter=meta_filter,
            )
            if results:
                all_results.extend(results)

    resource_context = "\n".join([r.text for r in all_results]) if all_results else "No resources found in database."

    campaign_context = ""
    if org_id:
        campaign_query = f"{big_idea} {content_tone} resource execution"
        campaign_results = await retrieve_campaign_knowledge(
            query=campaign_query,
            org_id=org_id,
            profile_name="resource_reference",
        )
        campaign_context = format_campaign_context(campaign_results, max_records=3)

    channel_names = [c.get("name", "") if isinstance(c, dict) else str(c) for c in channels]
    user_msg = (
        f"Big Idea: {big_idea}\n"
        f"Content Tone: {content_tone or 'not specified'}\n"
        f"Target Audience: {audience_insight or 'not specified'}\n"
        f"Category: {category or 'not specified'}\n"
        f"Channels: {', '.join(channel_names)}\n"
        f"Required resource types: {', '.join(resource_types_needed)}\n\n"
        f"Resource database results:\n{resource_context}"
    )
    if media_plan:
        tiers = media_plan.get("tiers", [])
        if tiers:
            tier_lines = []
            for t in tiers:
                tier_lines.append(
                    f"  - {t.get('channel', '?')} / {t.get('tier', '?')} tier: "
                    f"count={t.get('count', '?')}, role={t.get('role', '?')}, "
                    f"criteria: {t.get('selection_criteria', 'N/A')}"
                )
            user_msg += "\n\nMedia Plan (confirmed tier matrix — match resources to these requirements):\n" + "\n".join(tier_lines)
    if campaign_context:
        user_msg += f"\n\nHistorical campaign references (for context, not constraints):\n{campaign_context}"
    messages = [
        SystemMessage(content=SYSTEM_PROMPT[lang]),
        HumanMessage(content=user_msg),
    ]

    result = await invoke_llm_structured(
        messages, output_schema=ResourceResult, budget=budget, temperature=0.2, max_tokens=2048
    )

    result = await _validate_recommendations(result, client_id=client_id, org_id=org_id or "")
    return result
