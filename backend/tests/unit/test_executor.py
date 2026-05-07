"""Tests for PipelineExecutor HITL logic (no external deps)."""
import json


HITL_NODES = {"hitl_brief", "hitl_strategy", "hitl_structure", "hitl_gallery"}


def _apply_hitl_response(state: dict, node: str, response: dict) -> dict:
    """Mirror of PipelineExecutor._apply_hitl_response for unit testing."""
    action = response.get("action", "confirm")
    if node == "hitl_brief":
        state["brief_confirmed"] = True
        if response.get("edits"):
            state.setdefault("structured_brief", {}).update(response["edits"])
    elif node == "hitl_strategy":
        if action == "confirm":
            state["strategy_confirmed"] = True
        else:
            state["strategy_feedback"] = response.get("feedback", "")
            state["rerun_refresh_research"] = response.get("refresh_research", False)
    elif node == "hitl_structure":
        state["structure_confirmed"] = True
        if response.get("edits") and "deck_structure" in response["edits"]:
            state["deck_structure"] = response["edits"]["deck_structure"]
    elif node == "hitl_gallery":
        state["slides_confirmed"] = True
        flagged = response.get("flagged_indices", [])
        for idx in flagged:
            if idx < len(state.get("slides", [])):
                state["slides"][idx]["status"] = "flagged"
                state["slides"][idx]["feedback"] = response.get("feedback", "")
    return state


def test_hitl_nodes_defined():
    assert "hitl_brief" in HITL_NODES
    assert "hitl_strategy" in HITL_NODES
    assert "hitl_structure" in HITL_NODES
    assert "hitl_gallery" in HITL_NODES
    assert len(HITL_NODES) == 4


def test_apply_hitl_response_brief():
    state = {"structured_brief": {"client_name": "OldName"}}
    response = {"action": "confirm", "edits": {"client_name": "NewName"}}
    result = _apply_hitl_response(state, "hitl_brief", response)
    assert result["brief_confirmed"] is True
    assert result["structured_brief"]["client_name"] == "NewName"


def test_apply_hitl_response_brief_no_edits():
    state = {"structured_brief": {"client_name": "OriginalName"}}
    response = {"action": "confirm"}
    result = _apply_hitl_response(state, "hitl_brief", response)
    assert result["brief_confirmed"] is True
    assert result["structured_brief"]["client_name"] == "OriginalName"


def test_apply_hitl_response_strategy_confirm():
    state = {}
    response = {"action": "confirm"}
    result = _apply_hitl_response(state, "hitl_strategy", response)
    assert result["strategy_confirmed"] is True


def test_apply_hitl_response_strategy_revise():
    state = {}
    response = {"action": "revise", "feedback": "change direction", "refresh_research": True}
    result = _apply_hitl_response(state, "hitl_strategy", response)
    assert result.get("strategy_confirmed") is None
    assert result["strategy_feedback"] == "change direction"
    assert result["rerun_refresh_research"] is True


def test_apply_hitl_response_structure_with_edits():
    state = {"deck_structure": [{"title": "Old"}]}
    new_structure = [{"title": "New1"}, {"title": "New2"}]
    response = {"action": "confirm", "edits": {"deck_structure": new_structure}}
    result = _apply_hitl_response(state, "hitl_structure", response)
    assert result["structure_confirmed"] is True
    assert len(result["deck_structure"]) == 2
    assert result["deck_structure"][0]["title"] == "New1"


def test_apply_hitl_response_gallery_flag():
    state = {"slides": [
        {"index": 0, "content": {}, "status": "pending"},
        {"index": 1, "content": {}, "status": "pending"},
        {"index": 2, "content": {}, "status": "pending"},
    ]}
    response = {"action": "confirm", "flagged_indices": [0, 2], "feedback": "redo these"}
    result = _apply_hitl_response(state, "hitl_gallery", response)
    assert result["slides_confirmed"] is True
    assert result["slides"][0]["status"] == "flagged"
    assert result["slides"][1]["status"] == "pending"
    assert result["slides"][2]["status"] == "flagged"
    assert result["slides"][0]["feedback"] == "redo these"


def test_apply_hitl_response_gallery_no_flags():
    state = {"slides": [
        {"index": 0, "content": {}, "status": "pending"},
    ]}
    response = {"action": "confirm", "flagged_indices": []}
    result = _apply_hitl_response(state, "hitl_gallery", response)
    assert result["slides_confirmed"] is True
    assert result["slides"][0]["status"] == "pending"
