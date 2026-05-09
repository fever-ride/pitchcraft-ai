"""
End-to-end pipeline integration tests.
Requires: docker compose up -d (all services running)
Run: pytest backend/tests/integration/ -v --timeout=120
"""
import asyncio
import json
import time

import httpx
import pytest
import websockets

BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws"

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def auth_token():
    """Get a valid JWT token via test login."""
    resp = httpx.post(f"{BASE_URL}/api/v1/auth/login", json={
        "email": "test@pitchcraft.ai",
        "password": "testpass123",
    })
    if resp.status_code != 200:
        pytest.skip("Auth service not available or test user not seeded")
    return resp.json()["access_token"]


@pytest.fixture
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


class TestHealthChecks:
    def test_basic_health(self):
        resp = httpx.get(f"{BASE_URL}/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_detailed_health(self, headers):
        resp = httpx.get(f"{BASE_URL}/health/detailed", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["checks"]["mongodb"] == "ok"
        assert data["checks"]["redis"] == "ok"


class TestPipelineExecution:
    def test_start_pipeline(self, headers):
        resp = httpx.post(f"{BASE_URL}/api/v1/pipeline/start", headers=headers, json={
            "client_id": "test-client-001",
            "project_id": "test-project-001",
            "raw_brief": "为某国际美妆品牌策划一场618大促campaign，目标TA是18-25岁Z世代女性，预算50万，包含小红书+抖音双平台种草",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "pipeline_id" in data

    def test_pipeline_status(self, headers):
        # Start a pipeline
        start_resp = httpx.post(f"{BASE_URL}/api/v1/pipeline/start", headers=headers, json={
            "client_id": "test-client-002",
            "project_id": "test-project-002",
            "raw_brief": "Help client launch new product in Southeast Asia",
        })
        pipeline_id = start_resp.json()["pipeline_id"]

        # Wait briefly for pipeline to start
        time.sleep(2)

        # Check status
        status_resp = httpx.get(
            f"{BASE_URL}/api/v1/pipeline/{pipeline_id}/status", headers=headers
        )
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["status"] in ("running", "paused", "completed", "error")


class TestVersionManagement:
    def test_versions_empty(self, headers):
        resp = httpx.get(
            f"{BASE_URL}/api/v1/proposals/nonexistent-id/versions", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json() == []


class TestAnalytics:
    def test_pipeline_metrics(self, headers):
        resp = httpx.get(f"{BASE_URL}/api/v1/analytics/pipeline-metrics", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "pipeline_count" in data

    def test_cache_stats(self, headers):
        resp = httpx.get(f"{BASE_URL}/api/v1/analytics/cache-stats", headers=headers)
        assert resp.status_code == 200
        assert "cached_research_entries" in resp.json()

    def test_feedback_stats(self, headers):
        resp = httpx.get(f"{BASE_URL}/api/v1/analytics/feedback-stats", headers=headers)
        assert resp.status_code == 200


class TestFileUpload:
    def test_upload_requires_client_id(self, headers):
        resp = httpx.post(
            f"{BASE_URL}/api/v1/files/upload",
            headers=headers,
            data={"file_type": "brand_spec"},
            files={"file": ("test.pdf", b"%PDF-1.4 test content", "application/pdf")},
        )
        # Should fail without client_id
        assert resp.status_code in (400, 422)


class TestResourceLibrary:
    def test_list_resources(self, headers):
        resp = httpx.get(
            f"{BASE_URL}/api/v1/resources?client_id=test-client-001", headers=headers
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
