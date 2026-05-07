from backend.core.database.repositories.base import BaseRepository


class ResourceRepository(BaseRepository):
    collection_name = "resources"

    async def find_by_type(self, resource_type: str) -> list[dict]:
        return await self.find({"type": resource_type})

    async def find_by_tags(self, resource_type: str, tags: list[str]) -> list[dict]:
        return await self.find({
            "type": resource_type,
            "tags": {"$in": tags},
        })
