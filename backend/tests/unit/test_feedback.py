"""Tests for feedback model and rerun suggestion logic."""
from backend.core.models.feedback import RERUN_SUGGESTIONS, FeedbackTarget


def test_feedback_target_values():
    assert FeedbackTarget.STRATEGY == "strategy"
    assert FeedbackTarget.STRUCTURE == "structure"
    assert FeedbackTarget.SLIDE == "slide"
    assert FeedbackTarget.RESOURCE == "resource"
    assert FeedbackTarget.OVERALL == "overall"


def test_rerun_suggestion_strategy():
    assert RERUN_SUGGESTIONS[FeedbackTarget.STRATEGY] == "strategy_phase2"


def test_rerun_suggestion_structure():
    assert RERUN_SUGGESTIONS[FeedbackTarget.STRUCTURE] == "deck_orchestrator"


def test_rerun_suggestion_slide():
    assert RERUN_SUGGESTIONS[FeedbackTarget.SLIDE] == "slide_content"


def test_rerun_suggestion_resource():
    assert RERUN_SUGGESTIONS[FeedbackTarget.RESOURCE] == "resource_agent"


def test_rerun_suggestion_overall():
    assert RERUN_SUGGESTIONS[FeedbackTarget.OVERALL] == "strategy_phase2"


def test_all_targets_have_rerun_suggestion():
    for target in FeedbackTarget:
        assert target in RERUN_SUGGESTIONS


# --- Executor rerun logic (inlined) ---

def _apply_hitl_response(state: dict, node: str, response: dict) -> dict:
    """Mirrors executor._apply_hitl_response"""
    action = response.get("action", "confirm")
    if action == "rerun":
        state["rerun_from"] = response.get("rerun_from", "")
        return state
    if node == "hitl_brief":
        state["brief_confirmed"] = True
        if response.get("edits"):
            state.setdefault("structured_brief", {}).update(response["edits"])
    return state


def test_rerun_action_sets_rerun_from():
    state = {"client_id": "test"}
    result = _apply_hitl_response(state, "hitl_strategy", {"action": "rerun", "rerun_from": "resource_agent"})
    assert result["rerun_from"] == "resource_agent"


def test_rerun_action_skips_normal_processing():
    state = {"client_id": "test", "strategy_confirmed": False}
    result = _apply_hitl_response(state, "hitl_strategy", {"action": "rerun", "rerun_from": "strategy_phase2"})
    assert "strategy_confirmed" not in result or result["strategy_confirmed"] is False
    assert result["rerun_from"] == "strategy_phase2"


# --- Node sequence skip logic (inlined) ---

def test_start_from_skips_earlier_nodes():
    node_sequence = [
        ("brief_analyzer", None),
        ("hitl_brief", None),
        ("parallel_research_strategy", None),
        ("strategy_phase2", None),
        ("brand_check", None),
        ("hitl_strategy", None),
        ("resource_agent", None),
        ("deck_orchestrator", None),
    ]
    start_from = "resource_agent"
    node_names = [n[0] for n in node_sequence]
    start_idx = node_names.index(start_from)
    trimmed = node_sequence[start_idx:]

    assert trimmed[0][0] == "resource_agent"
    assert len(trimmed) == 2


def test_start_from_none_runs_all():
    node_sequence = [("a", None), ("b", None), ("c", None)]
    start_from = None
    if start_from:
        node_names = [n[0] for n in node_sequence]
        start_idx = node_names.index(start_from)
        node_sequence = node_sequence[start_idx:]
    assert len(node_sequence) == 3
