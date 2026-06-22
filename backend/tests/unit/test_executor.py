"""Tests for LangGraph pipeline: rerun predecessors, graph structure, HITL nodes."""
import json

import pytest

from backend.core.graph.executor import _RERUN_PREDECESSORS
from backend.core.graph.pipeline import (
    _CANONICAL_SEQUENCE,
    build_compiled_pipeline,
)
from backend.core.graph.state import BudgetExceeded, RequestBudget


# ---------------------------------------------------------------------------
# HITL node registry
# ---------------------------------------------------------------------------

HITL_NODES = {n for n in _CANONICAL_SEQUENCE if n.startswith("hitl_")}


def test_hitl_nodes_are_all_five():
    """All 5 HITL checkpoints must be present (including hitl_media)."""
    assert HITL_NODES == {
        "hitl_brief",
        "hitl_strategy",
        "hitl_media",
        "hitl_structure",
        "hitl_gallery",
    }


def test_canonical_sequence_order():
    """Verify the canonical ordering of key milestones."""
    seq = _CANONICAL_SEQUENCE
    assert seq.index("brief_analyzer") < seq.index("hitl_brief")
    assert seq.index("hitl_brief") < seq.index("research_agent")
    assert seq.index("hitl_strategy") < seq.index("media_planner")
    assert seq.index("hitl_media") < seq.index("resource_agent")
    assert seq.index("resource_agent") < seq.index("deck_orchestrator")
    assert seq.index("hitl_structure") < seq.index("slide_content")
    assert seq.index("narrative_agent") < seq.index("hitl_gallery")
    assert seq.index("hitl_gallery") < seq.index("ppt_builder")


# ---------------------------------------------------------------------------
# _RERUN_PREDECESSORS: LangGraph-native rerun mapping
# ---------------------------------------------------------------------------

def test_rerun_predecessors_covers_all_nodes():
    """Every node in the canonical sequence has an entry in _RERUN_PREDECESSORS."""
    for node in _CANONICAL_SEQUENCE:
        assert node in _RERUN_PREDECESSORS, f"Missing predecessor entry for '{node}'"


def test_brief_analyzer_has_no_predecessors():
    """Entry node has no predecessors to simulate."""
    assert _RERUN_PREDECESSORS["brief_analyzer"] == []


def test_strategy_phase2_has_two_predecessors():
    """Fan-in node needs both predecessors simulated."""
    preds = _RERUN_PREDECESSORS["strategy_phase2"]
    assert "research_agent" in preds
    assert "strategy_phase1" in preds
    assert len(preds) == 2


def test_all_predecessors_are_valid_nodes():
    """Every listed predecessor must itself be a node in the canonical sequence."""
    for node, preds in _RERUN_PREDECESSORS.items():
        for pred in preds:
            assert pred in _CANONICAL_SEQUENCE, (
                f"Predecessor '{pred}' of '{node}' is not in _CANONICAL_SEQUENCE"
            )


def test_predecessor_always_precedes_target():
    """Each predecessor must come before its target in the canonical sequence."""
    for node, preds in _RERUN_PREDECESSORS.items():
        node_idx = _CANONICAL_SEQUENCE.index(node)
        for pred in preds:
            pred_idx = _CANONICAL_SEQUENCE.index(pred)
            assert pred_idx < node_idx, (
                f"Predecessor '{pred}' (idx {pred_idx}) should come before "
                f"'{node}' (idx {node_idx})"
            )


# ---------------------------------------------------------------------------
# build_compiled_pipeline
# ---------------------------------------------------------------------------

def test_build_compiled_pipeline_returns_graph():
    """Smoke test: the compiled graph has the expected nodes."""
    graph = build_compiled_pipeline()
    node_names = set(graph.builder.nodes.keys())
    assert "brief_analyzer" in node_names
    assert "hitl_brief" in node_names
    assert "hitl_media" in node_names
    assert "ppt_builder" in node_names


def test_build_compiled_pipeline_with_custom_checkpointer():
    """Passing a custom checkpointer should not raise."""
    from langgraph.checkpoint.memory import MemorySaver
    graph = build_compiled_pipeline(checkpointer=MemorySaver())
    assert graph is not None


def test_no_direct_slide_content_to_hitl_gallery_edge():
    """slide_content should NOT have a direct edge to hitl_gallery (fixed topology)."""
    graph = build_compiled_pipeline()
    direct = any(
        getattr(e, "source", None) == "slide_content"
        and getattr(e, "target", None) == "hitl_gallery"
        for e in graph.builder.edges
    )
    assert not direct, "slide_content must not have a direct edge to hitl_gallery"


# ---------------------------------------------------------------------------
# aupdate_state + astream(None) — LangGraph native rerun
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_native_rerun_skips_predecessor_nodes():
    """_prime_checkpointer_for_rerun should make astream(None) start at the target node."""
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import StateGraph, END
    from typing import TypedDict

    class S(TypedDict, total=False):
        val: int

    runs: list[str] = []

    def node_a(s): runs.append("a"); return {"val": 1}
    def node_b(s): runs.append("b"); return {"val": (s.get("val") or 0) + 10}
    def node_c(s): runs.append("c"); return {"val": (s.get("val") or 0) + 100}

    g = StateGraph(S)
    g.add_node("a", node_a); g.add_node("b", node_b); g.add_node("c", node_c)
    g.set_entry_point("a")
    g.add_edge("a", "b"); g.add_edge("b", "c"); g.add_edge("c", END)
    graph = g.compile(checkpointer=MemorySaver())

    config = {"configurable": {"thread_id": "test_rerun"}}
    saved_state = {"val": 5}  # what Redis would have stored

    # Prime: simulate node "a" having run
    await graph.aupdate_state(config, saved_state, as_node="a")
    snap = await graph.aget_state(config)
    assert snap.next == ("b",)

    # Stream from None — should start at "b", not "a"
    async for _ in graph.astream(None, config=config, stream_mode="updates"):
        pass

    assert "a" not in runs, "node a should NOT have re-run"
    assert "b" in runs
    assert "c" in runs
    snap = await graph.aget_state(config)
    assert snap.values["val"] == 115  # 5 + 10 + 100


@pytest.mark.asyncio
async def test_native_rerun_fan_in():
    """Fan-in node becomes next after both predecessors are simulated."""
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import StateGraph, END
    from typing import TypedDict

    class S(TypedDict, total=False):
        r: str
        p: str
        combined: str

    ran: list[str] = []

    def r_node(s): ran.append("research"); return {"r": "new_research"}
    def p_node(s): ran.append("phase1"); return {"p": "new_phase1"}
    def phase2(s): ran.append("phase2"); return {"combined": f'{s.get("r")}+{s.get("p")}'}
    def end_node(s): ran.append("end"); return {}

    g = StateGraph(S)
    g.add_node("research_agent", r_node)
    g.add_node("strategy_phase1", p_node)
    g.add_node("strategy_phase2", phase2)
    g.add_node("end_node", end_node)
    g.set_entry_point("research_agent")
    g.add_edge("research_agent", "strategy_phase2")
    g.add_edge("strategy_phase1", "strategy_phase2")
    g.add_edge("strategy_phase2", "end_node")
    g.add_edge("end_node", END)
    graph = g.compile(checkpointer=MemorySaver())

    config = {"configurable": {"thread_id": "test_fanin"}}
    saved_state = {"r": "old_research", "p": "old_phase1"}

    # Simulate both predecessors
    await graph.aupdate_state(config, saved_state, as_node="research_agent")
    await graph.aupdate_state(config, saved_state, as_node="strategy_phase1")
    snap = await graph.aget_state(config)
    assert snap.next == ("strategy_phase2",)

    async for _ in graph.astream(None, config=config, stream_mode="updates"):
        pass

    assert "research_agent" not in ran
    assert "strategy_phase1" not in ran
    assert "phase2" in ran
    assert "end" in ran


# ---------------------------------------------------------------------------
# RequestBudget serialization safety
# ---------------------------------------------------------------------------

def test_request_budget_excluded_from_json():
    """save_state must not fail on RequestBudget — we strip it before serializing."""
    state = {
        "client_id": "c1",
        "proposal_id": "p1",
        "request_budget": RequestBudget(),
    }
    serializable = {k: v for k, v in state.items() if k != "request_budget"}
    dumped = json.dumps(serializable)
    loaded = json.loads(dumped)
    assert loaded["client_id"] == "c1"
    assert "request_budget" not in loaded


def test_request_budget_recreated_after_reload():
    """Simulate load_state + run: missing budget → new RequestBudget created."""
    loaded_state = {"client_id": "c1", "proposal_id": "p1"}
    if not isinstance(loaded_state.get("request_budget"), RequestBudget):
        loaded_state["request_budget"] = RequestBudget()
    assert isinstance(loaded_state["request_budget"], RequestBudget)
    assert loaded_state["request_budget"].current_llm_calls == 0


# ---------------------------------------------------------------------------
# hitl_strategy_node response mapping (inline logic mirror)
# ---------------------------------------------------------------------------

def _apply_hitl_strategy(response: dict) -> dict:
    """Mirror of hitl_strategy_node resume-branch logic for unit testing."""
    action = response.get("action", "confirm")
    if action == "rerun":
        return {
            "rerun_from": response.get("rerun_from", ""),
            "rerun_refresh_research": response.get("refresh_research", False),
        }
    if action == "confirm":
        return {"strategy_confirmed": True}
    return {
        "strategy_confirmed": False,
        "strategy_feedback": response.get("feedback", ""),
        "rerun_refresh_research": response.get("refresh_research", False),
    }


def test_strategy_confirm():
    result = _apply_hitl_strategy({"action": "confirm"})
    assert result == {"strategy_confirmed": True}


def test_strategy_revise_captures_refresh_research():
    result = _apply_hitl_strategy({
        "action": "revise",
        "feedback": "change direction",
        "refresh_research": True,
    })
    assert result["strategy_confirmed"] is False
    assert result["strategy_feedback"] == "change direction"
    assert result["rerun_refresh_research"] is True


def test_strategy_revise_defaults_refresh_to_false():
    result = _apply_hitl_strategy({"action": "revise", "feedback": "needs work"})
    assert result["rerun_refresh_research"] is False


def test_strategy_rerun_sets_rerun_from():
    """rerun action must set rerun_from so _stream_run can detect it."""
    result = _apply_hitl_strategy({
        "action": "rerun",
        "rerun_from": "strategy_phase1",
        "refresh_research": True,
    })
    assert result["rerun_from"] == "strategy_phase1"
    assert result["rerun_refresh_research"] is True
    assert "strategy_confirmed" not in result


# ---------------------------------------------------------------------------
# hitl_media: edits flow
# ---------------------------------------------------------------------------

def _apply_hitl_media(state: dict, response: dict) -> dict:
    """Mirror of hitl_media_node resume-branch logic."""
    updates: dict = {"media_plan_confirmed": True}
    if response.get("edits") and "media_plan" in response["edits"]:
        updates["media_plan"] = response["edits"]["media_plan"]
    return updates


def test_media_confirm_no_edits():
    result = _apply_hitl_media({}, {"action": "confirm"})
    assert result["media_plan_confirmed"] is True
    assert "media_plan" not in result


def test_media_confirm_with_edits():
    new_plan = {"tiers": [{"channel": "douyin", "tier": "top"}]}
    result = _apply_hitl_media(
        {"media_plan": {}},
        {"action": "confirm", "edits": {"media_plan": new_plan}},
    )
    assert result["media_plan_confirmed"] is True
    assert result["media_plan"] == new_plan
