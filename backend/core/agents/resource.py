"""Resource Agent: multi-type resource matching based on typed strategy fields from state."""
from langchain_core.messages import HumanMessage, SystemMessage

from backend.core.agents.llm import invoke_llm_structured
from backend.core.agents.schemas import ResourceResult
from backend.core.database.connection import get_database
from backend.core.graph.state import RequestBudget
from backend.core.language.detector import resolve_output_language
from backend.core.models.resource import FRESHNESS_THRESHOLD_DAYS, ResourceStatus, resource_namespace
from backend.core.rag.retriever import retrieve

SYSTEM_PROMPT = {
    "zh": "你是资深媒介策划。基于策略方向和资源库检索结果，推荐最适合的资源组合。只推荐资源库中实际存在的资源，不要编造。可用类型：KOL/KOC、Media、Vendor、Placement。",
    "en": "You are a senior media planner. Based on the strategy direction and resource database results, recommend the most suitable resource mix. Only recommend resources that exist in the provided database results — do not invent names. Available types: KOL/KOC, Media, Vendor, Placement.",
}


async def _validate_recommendations(result: ResourceResult, client_id: str) -> ResourceResult:
    """Post-validation: verify recommended resources exist in MongoDB and are active."""
    if not result.recommended_resources:
        return result

    db = await get_database()
    collection = db["resources"]

    validated = []
    for rec in result.recommended_resources:
        doc = await collection.find_one({
            "client_id": client_id,
            "name": {"$regex": f"^{rec.name}$", "$options": "i"},
        })
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
    client_id: str,
    budget: RequestBudget | None = None,
    output_language: str = "auto",
) -> ResourceResult | dict:
    """Match resources from DB based on typed strategy fields.

    resource_types_needed comes directly from StrategyPhase2Result.resource_types,
    written to state by the strategy_phase2 node. No re-detection needed.
    """
    if not resource_types_needed:
        return {"skipped": True, "reason": "No resource types specified by strategy"}

    lang = resolve_output_language(output_language, big_idea)

    channel_names = [c.get("name", "") if isinstance(c, dict) else str(c) for c in channels]
    search_query = f"{big_idea} {' '.join(channel_names)} {' '.join(resource_types_needed)}"

    all_results = []
    for rtype in resource_types_needed:
        ns = resource_namespace(rtype, client_id)
        results = await retrieve(
            query=search_query,
            namespaces=[ns],
            top_k=8,
            score_threshold=0.3,
        )
        if results:
            all_results.extend(results)

    resource_context = "\n".join([r.text for r in all_results]) if all_results else "No resources found in database."

    user_msg = (
        f"Big Idea: {big_idea}\n"
        f"Channels: {', '.join(channel_names)}\n"
        f"Required resource types: {', '.join(resource_types_needed)}\n\n"
        f"Resource database results:\n{resource_context}"
    )
    messages = [
        SystemMessage(content=SYSTEM_PROMPT[lang]),
        HumanMessage(content=user_msg),
    ]

    result = await invoke_llm_structured(
        messages, output_schema=ResourceResult, budget=budget, temperature=0.2, max_tokens=2048
    )

    result = await _validate_recommendations(result, client_id)
    return result
