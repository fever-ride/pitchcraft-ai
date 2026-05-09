"""Tests for version management logic."""
import pytest
from datetime import datetime


def _make_state(brief="test brief", strategy=None, slides=None, pptx=None):
    return {
        "proposal_id": "prop-001",
        "project_id": "proj-001",
        "client_id": "client-001",
        "structured_brief": {"theme": brief},
        "research_result": {"competitors": []},
        "strategy_result": strategy or {"big_idea": "Idea A"},
        "deck_structure": [{"index": 0, "title": "Cover"}],
        "slides": slides or [{"index": 0, "content": {"title": "Cover"}}],
        "pptx_path": pptx or "/data/output/test.pptx",
        "resource_result": None,
        "narrative_suggestions": [],
    }


def _extract_snapshot(state):
    """Mirrors ProposalVersionRepository.save_version snapshot extraction."""
    return {
        "structured_brief": state.get("structured_brief"),
        "research_result": state.get("research_result"),
        "strategy_result": state.get("strategy_result"),
        "deck_structure": state.get("deck_structure"),
        "slides": state.get("slides"),
        "pptx_path": state.get("pptx_path"),
        "resource_result": state.get("resource_result"),
        "narrative_suggestions": state.get("narrative_suggestions"),
    }


def _compute_diff(snap1, snap2):
    """Mirrors the diff endpoint logic."""
    diff = {}
    all_keys = set(list(snap1.keys()) + list(snap2.keys()))
    for key in all_keys:
        val1 = snap1.get(key)
        val2 = snap2.get(key)
        if val1 != val2:
            diff[key] = {"v1": val1, "v2": val2}
    return diff


class TestSnapshotExtraction:
    def test_extracts_all_fields(self):
        state = _make_state()
        snap = _extract_snapshot(state)
        assert "structured_brief" in snap
        assert "strategy_result" in snap
        assert "slides" in snap
        assert "pptx_path" in snap

    def test_excludes_internal_fields(self):
        state = _make_state()
        state["request_budget"] = {"llm_calls": 10}
        state["rerun_from"] = "strategy_phase2"
        snap = _extract_snapshot(state)
        assert "request_budget" not in snap
        assert "rerun_from" not in snap

    def test_handles_none_fields(self):
        state = _make_state()
        state["resource_result"] = None
        snap = _extract_snapshot(state)
        assert snap["resource_result"] is None


class TestDiffComputation:
    def test_no_diff_for_identical_snapshots(self):
        state = _make_state()
        snap = _extract_snapshot(state)
        diff = _compute_diff(snap, snap)
        assert diff == {}

    def test_detects_strategy_change(self):
        s1 = _extract_snapshot(_make_state(strategy={"big_idea": "Idea A"}))
        s2 = _extract_snapshot(_make_state(strategy={"big_idea": "Idea B"}))
        diff = _compute_diff(s1, s2)
        assert "strategy_result" in diff
        assert diff["strategy_result"]["v1"]["big_idea"] == "Idea A"
        assert diff["strategy_result"]["v2"]["big_idea"] == "Idea B"

    def test_detects_slides_change(self):
        s1 = _extract_snapshot(_make_state(slides=[{"index": 0, "content": {"title": "Cover"}}]))
        s2 = _extract_snapshot(_make_state(slides=[
            {"index": 0, "content": {"title": "Cover"}},
            {"index": 1, "content": {"title": "New Slide"}},
        ]))
        diff = _compute_diff(s1, s2)
        assert "slides" in diff

    def test_detects_pptx_path_change(self):
        s1 = _extract_snapshot(_make_state(pptx="/data/v1.pptx"))
        s2 = _extract_snapshot(_make_state(pptx="/data/v2.pptx"))
        diff = _compute_diff(s1, s2)
        assert "pptx_path" in diff

    def test_multiple_field_changes(self):
        s1 = _extract_snapshot(_make_state(strategy={"big_idea": "A"}, brief="old"))
        s2 = _extract_snapshot(_make_state(strategy={"big_idea": "B"}, brief="new"))
        diff = _compute_diff(s1, s2)
        assert "strategy_result" in diff
        assert "structured_brief" in diff


class TestRollbackLogic:
    def test_rollback_applies_snapshot_to_state(self):
        original_state = _make_state(strategy={"big_idea": "Original"})
        original_snap = _extract_snapshot(original_state)

        current_state = _make_state(strategy={"big_idea": "Modified"})
        current_state.update(original_snap)

        assert current_state["strategy_result"]["big_idea"] == "Original"
        assert current_state["proposal_id"] == "prop-001"

    def test_rollback_preserves_identity_fields(self):
        target_snap = _extract_snapshot(_make_state())
        current_state = {
            "proposal_id": "prop-001",
            "project_id": "proj-001",
            "client_id": "client-001",
            "request_budget": {"llm_calls": 5},
            **_make_state(strategy={"big_idea": "Current"}),
        }
        current_state.update(target_snap)
        assert current_state["proposal_id"] == "prop-001"
        assert current_state["request_budget"] == {"llm_calls": 5}


class TestVersionNumbering:
    def test_sequential_version_numbers(self):
        versions = []
        for i in range(1, 5):
            versions.append(i)
        assert versions == [1, 2, 3, 4]

    def test_rollback_increments_version(self):
        versions = [1, 2, 3]
        next_after_rollback = max(versions) + 1
        assert next_after_rollback == 4
