from backend.core.database.repositories.base import BaseRepository


class StageMetricsRepository(BaseRepository):
    collection_name = "stage_metrics"

    async def find_by_project(self, project_id: str) -> list[dict]:
        return await self.find({"project_id": project_id})

    async def find_by_client(self, client_id: str) -> list[dict]:
        return await self.find({"client_id": client_id})
