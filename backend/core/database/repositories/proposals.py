from backend.core.database.repositories.base import BaseRepository


class ProposalRepository(BaseRepository):
    collection_name = "proposals"

    async def find_by_project(self, project_id: str) -> list[dict]:
        return await self.find({"project_id": project_id})

    async def get_latest_version(self, project_id: str) -> int:
        doc = await self.collection.find_one(
            {"project_id": project_id},
            sort=[("version", -1)],
        )
        if doc:
            return doc["version"]
        return 0
