"""Unit tests for POST /api/v1/pipeline/{id}/confirm validation."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.v1.endpoints.pipeline import get_current_user


class _FakeUser:
    organization_id = "org-test"


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: _FakeUser()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _patch_executor(status: str, current_node: str | None):
    executor = MagicMock()
    executor.get_status = AsyncMock(
        return_value={"status": status, "current_node": current_node},
    )
    executor.set_status = AsyncMock()
    executor.resume_pipeline = AsyncMock()
    return patch(
        "backend.api.v1.endpoints.pipeline.PipelineExecutor",
        return_value=executor,
    ), executor


def test_confirm_rejects_when_not_paused(client):
    patcher, _ = _patch_executor("running", "hitl_brief")
    with patcher:
        resp = client.post(
            "/api/v1/pipeline/pipe-1/confirm",
            json={"node": "hitl_brief", "action": "confirm"},
        )
    assert resp.status_code == 400
    assert "not paused" in resp.json()["detail"]


def test_confirm_rejects_wrong_node(client):
    patcher, _ = _patch_executor("paused", "hitl_strategy")
    with patcher:
        resp = client.post(
            "/api/v1/pipeline/pipe-1/confirm",
            json={"node": "hitl_brief", "action": "confirm"},
        )
    assert resp.status_code == 400
    assert "hitl_strategy" in resp.json()["detail"]


def test_confirm_accepts_matching_node_and_locks_running(client):
    patcher, executor = _patch_executor("paused", "hitl_brief")
    with patcher:
        resp = client.post(
            "/api/v1/pipeline/pipe-1/confirm",
            json={"node": "hitl_brief", "action": "confirm"},
        )
    assert resp.status_code == 202
    assert resp.json()["status"] == "accepted"
    executor.set_status.assert_awaited_once_with("running", "hitl_brief")


def test_confirm_rejects_second_submit_while_running(client):
    """After optimistic lock, status is running — duplicate confirm is rejected."""
    patcher, _ = _patch_executor("running", "hitl_brief")
    with patcher:
        resp = client.post(
            "/api/v1/pipeline/pipe-1/confirm",
            json={"node": "hitl_brief", "action": "confirm"},
        )
    assert resp.status_code == 400
