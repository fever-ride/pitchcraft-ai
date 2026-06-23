import asyncio
import json
import time

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from backend.core.agents.brief_analyzer import analyze_brief
from backend.core.agents.deck import (
    generate_slide_content,
    run_deck_orchestrator,
    run_narrative_check,
)
from backend.core.agents.media_planner import run_media_planner
from backend.core.agents.ppt_builder import build_pptx
from backend.core.agents.research import run_research
from backend.core.agents.resource import run_resource_agent
from backend.core.agents.strategy import (
    run_brand_check,
    run_strategy_phase1,
    run_strategy_phase2,
)
from backend.core.graph.state import PipelineState

# Canonical node execution order — used by PipelineExecutor for rerun predecessor lookup.
_CANONICAL_SEQUENCE = [
    "brief_analyzer",
    "hitl_brief",
    "research_agent",
    "strategy_phase1",
    "strategy_phase2",
    "brand_check",
    "hitl_strategy",
    "media_planner",
    "hitl_media",
    "resource_agent",
    "deck_orchestrator",
    "hitl_structure",
    "slide_content",
    "narrative_agent",
    "hitl_gallery",
    "ppt_builder",
]


def _route_after_hitl_media(state: PipelineState) -> str:
    """Skip resource_agent when no resource types are needed (e.g. internal pitch)."""
    if not state.get("resource_types_needed"):
        return "deck_orchestrator"
    return "resource_agent"


def build_pipeline() -> StateGraph:
    graph = StateGraph(PipelineState)

    graph.add_node("brief_analyzer", brief_analyzer_node)
    graph.add_node("hitl_brief", hitl_brief_node)
    graph.add_node("research_agent", research_agent_node)
    graph.add_node("strategy_phase1", strategy_phase1_node)
    graph.add_node("strategy_phase2", strategy_phase2_node)
    graph.add_node("brand_check", brand_check_node)
    graph.add_node("hitl_strategy", hitl_strategy_node)
    graph.add_node("media_planner", media_planner_node)
    graph.add_node("hitl_media", hitl_media_node)
    graph.add_node("resource_agent", resource_agent_node)
    graph.add_node("deck_orchestrator", deck_orchestrator_node)
    graph.add_node("hitl_structure", hitl_structure_node)
    graph.add_node("slide_content", slide_content_node)
    graph.add_node("narrative_agent", narrative_agent_node)
    graph.add_node("hitl_gallery", hitl_gallery_node)
    graph.add_node("ppt_builder", ppt_builder_node)

    graph.set_entry_point("brief_analyzer")

    graph.add_edge("brief_analyzer", "hitl_brief")

    # Fan-out: research and strategy phase 1 run in parallel after brief confirmation
    graph.add_edge("hitl_brief", "research_agent")
    graph.add_edge("hitl_brief", "strategy_phase1")

    # Fan-in: strategy phase 2 waits for both research and phase 1
    graph.add_edge("research_agent", "strategy_phase2")
    graph.add_edge("strategy_phase1", "strategy_phase2")

    graph.add_edge("strategy_phase2", "brand_check")
    graph.add_edge("brand_check", "hitl_strategy")

    graph.add_edge("hitl_strategy", "media_planner")
    graph.add_edge("media_planner", "hitl_media")

    # Conditional: skip resource_agent if resource_types_needed is empty
    graph.add_conditional_edges(
        "hitl_media",
        _route_after_hitl_media,
        {"resource_agent": "resource_agent", "deck_orchestrator": "deck_orchestrator"},
    )
    graph.add_edge("resource_agent", "deck_orchestrator")
    graph.add_edge("deck_orchestrator", "hitl_structure")

    graph.add_edge("hitl_structure", "slide_content")

    # Serial: narrative_agent runs after slide_content, hitl_gallery waits for narrative
    graph.add_edge("slide_content", "narrative_agent")
    graph.add_edge("narrative_agent", "hitl_gallery")

    graph.add_edge("hitl_gallery", "ppt_builder")
    graph.add_edge("ppt_builder", END)

    return graph


def build_compiled_pipeline(checkpointer=None):
    """Compile the pipeline graph with an optional checkpointer (defaults to MemorySaver)."""
    return build_pipeline().compile(checkpointer=checkpointer or MemorySaver())


async def brief_analyzer_node(state: PipelineState) -> dict:
    budget = state.get("request_budget")
    result = await analyze_brief(
        state["raw_brief"],
        budget=budget,
        client_id=state.get("client_id"),
        org_id=state.get("org_id"),
    )
    return {
        "structured_brief": result.structured_brief.model_dump(),
        "missing_fields": result.missing_fields,
        "clarification_questions": result.clarification_questions,
    }


async def hitl_brief_node(state: PipelineState) -> dict:
    response = interrupt({"structured_brief": state.get("structured_brief", {})})

    updates: dict = {}
    if response.get("edits"):
        merged = dict(state.get("structured_brief", {}))
        merged.update(response["edits"])
        updates["structured_brief"] = merged
    updates["brief_confirmed"] = True
    return updates


async def research_agent_node(state: PipelineState) -> dict:
    brief = state.get("structured_brief", {})
    force_refresh = state.get("rerun_refresh_research", False)
    budget = state.get("request_budget")
    competitor_names: list[str] = brief.get("competitors", [])
    result = await run_research(
        brief=brief,
        client_id=state["client_id"],
        org_id=state.get("org_id"),
        project_id=state.get("project_id"),
        force_refresh=force_refresh,
        budget=budget,
        competitor_names=competitor_names,
    )
    return {
        "research_result": result,
        "research_fetched_at": result.get("fetched_at", time.time()),
        "market_trends": result.get("market_trends", []),
        "opportunities": result.get("opportunities", []),
    }


async def strategy_phase1_node(state: PipelineState) -> dict:
    brief = state.get("structured_brief", {})
    budget = state.get("request_budget")
    result = await run_strategy_phase1(
        brief=brief,
        client_id=state["client_id"],
        project_id=state.get("project_id"),
        budget=budget,
    )
    result_dict = result.model_dump()
    return {
        "strategy_insight": result_dict,
        "audience_insight": result.audience_insight,
        "brand_direction": result.brand_direction,
    }


async def strategy_phase2_node(state: PipelineState) -> dict:
    brief = state.get("structured_brief", {})
    budget = state.get("request_budget")
    result = await run_strategy_phase2(
        brief=brief,
        phase1_insight=state.get("strategy_insight", {}),
        research_result=state.get("research_result", {}),
        client_id=state.get("client_id"),
        org_id=state.get("org_id"),
        budget=budget,
    )
    result_dict = result.model_dump()
    return {
        "strategy_result": result_dict,
        "big_idea": result.big_idea,
        "content_tone": result.content_tone,
        "channels": [c.model_dump() for c in result.channels],
        "resource_types_needed": result.resource_types,
        "kpis": result.kpis,
        "timeline_phases": [t.model_dump() for t in result.timeline_phases],
        "budget_allocation": result.budget_allocation,
    }


async def brand_check_node(state: PipelineState) -> dict:
    strategy_text = json.dumps(state.get("strategy_result", {}), ensure_ascii=False)
    budget = state.get("request_budget")
    result = await run_brand_check(
        strategy_text=strategy_text,
        client_id=state["client_id"],
        budget=budget,
    )
    return {"brand_check_passed": result.passed}


async def hitl_strategy_node(state: PipelineState) -> dict:
    response = interrupt({
        "strategy_result": state.get("strategy_result", {}),
        "research_result": state.get("research_result", {}),
        "brand_check_passed": state.get("brand_check_passed"),
    })

    action = response.get("action", "confirm")
    if action == "rerun":
        # Signal the executor to abort this run and restart from rerun_from.
        # PipelineExecutor._stream_run detects "rerun_from" in node updates and
        # uses aupdate_state + goto to restart natively — no skip-shim needed.
        return {
            "rerun_from": response.get("rerun_from", ""),
            "rerun_refresh_research": response.get("refresh_research", False),
        }
    if action == "confirm":
        return {"strategy_confirmed": True}
    # "revise" or any other action: store feedback + research flag for potential rerun
    return {
        "strategy_confirmed": False,
        "strategy_feedback": response.get("feedback", ""),
        "rerun_refresh_research": response.get("refresh_research", False),
    }


async def media_planner_node(state: PipelineState) -> dict:
    budget = state.get("request_budget")
    result = await run_media_planner(
        big_idea=state.get("big_idea", ""),
        channels=state.get("channels", []),
        budget_allocation=state.get("budget_allocation", {}),
        audience_insight=state.get("audience_insight", ""),
        content_tone=state.get("content_tone", ""),
        kpis=state.get("kpis"),
        budget=budget,
        output_language=state.get("output_language", "auto"),
        org_id=state.get("org_id"),
    )
    return {"media_plan": result.model_dump()}


async def hitl_media_node(state: PipelineState) -> dict:
    response = interrupt({"media_plan": state.get("media_plan", {})})

    updates: dict = {"media_plan_confirmed": True}
    if response.get("edits") and "media_plan" in response["edits"]:
        updates["media_plan"] = response["edits"]["media_plan"]
    return updates


async def resource_agent_node(state: PipelineState) -> dict:
    budget = state.get("request_budget")
    brief = state.get("structured_brief", {})
    result = await run_resource_agent(
        big_idea=state.get("big_idea", ""),
        channels=state.get("channels", []),
        resource_types_needed=state.get("resource_types_needed", []),
        client_id=state["client_id"],
        content_tone=state.get("content_tone", ""),
        audience_insight=state.get("audience_insight", ""),
        category=brief.get("category", ""),
        budget=budget,
        output_language=state.get("output_language", "auto"),
        org_id=state.get("org_id"),
        media_plan=state.get("media_plan"),
    )
    if isinstance(result, dict):
        return {"resource_result": result}
    return {"resource_result": result.model_dump()}


async def deck_orchestrator_node(state: PipelineState) -> dict:
    brief = state.get("structured_brief", {})
    budget = state.get("request_budget")
    structure = await run_deck_orchestrator(
        big_idea=state.get("big_idea", ""),
        channels=state.get("channels", []),
        kpis=state.get("kpis", []),
        brief=brief,
        client_id=state["client_id"],
        project_id=state.get("project_id"),
        budget=budget,
        output_language=state.get("output_language", "auto"),
        org_id=state.get("org_id"),
    )
    return {"deck_structure": structure}


async def hitl_structure_node(state: PipelineState) -> dict:
    response = interrupt({"deck_structure": state.get("deck_structure", [])})

    updates: dict = {"structure_confirmed": True}
    edits = response.get("edits", {})
    if edits and "deck_structure" in edits:
        updates["deck_structure"] = edits["deck_structure"]
    return updates


async def slide_content_node(state: PipelineState) -> dict:
    structure = state.get("deck_structure", [])
    big_idea = state.get("big_idea", "")
    brand_direction = state.get("brand_direction", "")
    client_id = state["client_id"]
    project_id = state.get("project_id")
    budget = state.get("request_budget")
    output_language = state.get("output_language", "auto")

    # On a feedback-driven rerun, existing slides that were not flagged are
    # preserved as-is. Only flagged slides (status="flagged") are regenerated,
    # with their user feedback injected as a revision constraint.
    existing_slides: list[dict] = state.get("slides", [])
    existing_by_index = {s["index"]: s for s in existing_slides}

    sem = asyncio.Semaphore(3)

    async def _generate_one(slide_info: dict, idx: int) -> dict:
        slide_index = slide_info.get("slide_index", idx)
        existing = existing_by_index.get(slide_index)

        # Reuse unchanged slides; regenerate only flagged ones.
        if existing and existing.get("status") != "flagged":
            return {**existing, "status": "pending"}

        feedback_note = (existing or {}).get("feedback", "") if existing else ""
        async with sem:
            content = await generate_slide_content(
                slide=slide_info,
                big_idea=big_idea,
                brand_direction=brand_direction,
                client_id=client_id,
                project_id=project_id,
                budget=budget,
                output_language=output_language,
                revision_feedback=feedback_note or None,
            )
        return {
            "index": slide_index,
            "content": content.model_dump(),
            "status": "pending",
        }

    tasks = [_generate_one(s, i) for i, s in enumerate(structure)]
    slides = await asyncio.gather(*tasks)

    return {"slides": list(slides)}


async def narrative_agent_node(state: PipelineState) -> dict:
    slides = state.get("slides", [])
    budget = state.get("request_budget")
    output_language = state.get("output_language", "auto")
    suggestions = await run_narrative_check(slides, budget=budget, output_language=output_language)
    return {"narrative_suggestions": suggestions}


async def hitl_gallery_node(state: PipelineState) -> dict:
    response = interrupt({
        "slides": state.get("slides", []),
        "narrative_suggestions": state.get("narrative_suggestions", []),
    })

    updates: dict = {"slides_confirmed": True}
    flagged = response.get("flagged_indices", [])
    if flagged:
        slides = list(state.get("slides", []))
        for idx in flagged:
            if idx < len(slides):
                slides[idx] = {
                    **slides[idx],
                    "status": "flagged",
                    "feedback": response.get("feedback", ""),
                }
        updates["slides"] = slides
    return updates


async def ppt_builder_node(state: PipelineState) -> dict:
    slides = state.get("slides", [])
    proposal_id = state.get("proposal_id", "draft")
    output_path = build_pptx(slides, proposal_id)
    return {"pptx_path": output_path}
