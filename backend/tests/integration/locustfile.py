"""
Load test: concurrent pipeline runs and budget enforcement.
Run: locust -f backend/tests/integration/locustfile.py --host=http://localhost:8000
"""
from locust import HttpUser, task, between


class PitchcraftUser(HttpUser):
    wait_time = between(2, 5)

    def on_start(self):
        resp = self.client.post("/api/v1/auth/login", json={
            "email": "test@pitchcraft.ai",
            "password": "testpass123",
        })
        if resp.status_code == 200:
            self.token = resp.json()["access_token"]
        else:
            self.token = "invalid"

    @property
    def auth_headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    @task(3)
    def health_check(self):
        self.client.get("/health")

    @task(2)
    def start_pipeline(self):
        self.client.post("/api/v1/pipeline/start", headers=self.auth_headers, json={
            "client_id": "load-test-client",
            "project_id": "load-test-project",
            "raw_brief": "Plan a social media campaign for a tech startup targeting millennials. Budget: 100k. Channels: Instagram, TikTok, LinkedIn.",
        })

    @task(2)
    def list_proposals(self):
        self.client.get(
            "/api/v1/proposals?project_id=load-test-project",
            headers=self.auth_headers,
        )

    @task(1)
    def get_analytics(self):
        self.client.get("/api/v1/analytics/pipeline-metrics", headers=self.auth_headers)

    @task(1)
    def list_resources(self):
        self.client.get(
            "/api/v1/resources?client_id=load-test-client",
            headers=self.auth_headers,
        )

    @task(1)
    def cache_stats(self):
        self.client.get("/api/v1/analytics/cache-stats", headers=self.auth_headers)
