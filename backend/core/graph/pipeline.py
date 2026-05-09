import json
import time

from langgraph.graph import END, StateGraph

from backend.core.agents.brief_analyzer import analyze_brief
from backend.core.agents.deck import (
    generate_slide_content,
    run_deck_orchestrator,
    run_narrative_check,
)
from backend.core.agents.ppt_builder import build_pptx
from backend.core.agents.research import run_research
from backend.core.agents.resource import run_resource_agent
from backend.core.agents.strategy import (
    run_brand_check,
    run_strategy_phase1,
    run_strategy_phase2,
)
from backend.core.graph.state import PipelineState


def build_pipeline() -> StateGraph:
    graph = StateGraph(PipelineState)

    graph.add_node("brief_analyzer", brief_analyzer_node)
    graph.add_node("hitl_brief", hitl_brief_node)
    graph.add_node("research_agent", research_agent_node)
    graph.add_node("strategy_phase1", strategy_phase1_node)
    graph.add_node("strategy_phase2", strategy_phase2_node)
    graph.add_node("brand_check", brand_check_node)
    graph.add_node("hitl_strategy", hitl_strategy_node)
    graph.add_node("resource_agent", resource_agent_node)
    graph.add_node("deck_orchestrator", deck_orchestrator_node)
    graph.add_node("hitl_structure", hitl_structure_node)
    graph.add_node("slide_content", slide_content_node)
    graph.add_node("narrative_agent", narrative_agent_node)
    graph.add_node("hitl_gallery", hitl_gallery_node)
    graph.add_node("ppt_builder", ppt_builder_node)

    graph.set_entry_point("brief_analyzer")

    graph.add_edge("brief_analyzer", "hitl_brief")

    graph.add_edge("hitl_brief", "research_agent")
    graph.add_edge("hitl_brief", "strategy_phase1")

    graph.add_edge("research_agent", "strategy_phase2")
    graph.add_edge("strategy_phase1", "strategy_phase2")

    graph.add_edge("strategy_phase2", "brand_check")
    graph.add_edge("brand_check", "hitl_strategy")

    graph.add_edge("hitl_strategy", "resource_agent")
    graph.add_edge("resource_agent", "deck_orchestrator")
    graph.add_edge("deck_orchestrator", "hitl_structure")

    graph.add_edge("hitl_structure", "slide_content")

    graph.add_edge("slide_content", "narrative_agent")
    graph.add_edge("slide_content", "hitl_gallery")
    graph.add_edge("narrative_agent", "hitl_gallery")

    graph.add_edge("hitl_gallery", "ppt_builder")
    graph.add_edge("ppt_builder", END)

    return graph


async def brief_analyzer_node(state: PipelineState) -> dict:
    budget = state.get("request_budget")
    result = await analyze_brief(state["raw_brief"], budget=budget)
    return {
        "structured_brief": result.structured_brief.model_dump(),
        "missing_fields": result.missing_fields,
        "clarification_questions": result.clarification_questions,
    }


async def hitl_brief_node(state: PipelineState) -> dict:
    return {}


async def research_agent_node(state: PipelineState) -> dict:
    brief = state.get("structured_brief", {})
    force_refresh = state.get("rerun_refresh_research", False)
    budget = state.get("request_budget")
    result = await run_research(
        brief=brief,
        client_id=state["client_id"],
        project_id=state.get("project_id"),
        force_refresh=force_refresh,
        budget=budget,
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
    return {}


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
    )
    return {"deck_structure": structure}


async def hitl_structure_node(state: PipelineState) -> dict:
    return {}


async def slide_content_node(state: PipelineState) -> dict:
    structure = state.get("deck_structure", [])
    big_idea = state.get("big_idea", "")
    brand_direction = state.get("brand_direction", "")
    client_id = state["client_id"]
    project_id = state.get("project_id")
    budget = state.get("request_budget")
    output_language = state.get("output_language", "auto")

    slides = []
    for slide_info in structure:
        content = await generate_slide_content(
            slide=slide_info,
            big_idea=big_idea,
            brand_direction=brand_direction,
            client_id=client_id,
            project_id=project_id,
            budget=budget,
            output_language=output_language,
        )
        slides.append({
            "index": slide_info.get("slide_index", len(slides)),
            "content": content.model_dump(),
            "status": "pending",
        })

    return {"slides": slides}


async def narrative_agent_node(state: PipelineState) -> dict:
    slides = state.get("slides", [])
    budget = state.get("request_budget")
    output_language = state.get("output_language", "auto")
    suggestions = await run_narrative_check(slides, budget=budget, output_language=output_language)
    return {"narrative_suggestions": suggestions}


async def hitl_gallery_node(state: PipelineState) -> dict:
    return {}


async def ppt_builder_node(state: PipelineState) -> dict:
    slides = state.get("slides", [])
    proposal_id = state.get("proposal_id", "draft")
    output_path = build_pptx(slides, proposal_id)
    return {"pptx_path": output_path}
