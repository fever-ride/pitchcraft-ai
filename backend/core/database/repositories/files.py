from backend.core.database.repositories.base import BaseRepository


class FileRepository(BaseRepository):
    collection_name = "files"

    async def find_by_client(self, client_id: str) -> list[dict]:
        return await self.find({"client_id": client_id, "deleted": {"$ne": True}})

    async def find_by_project(self, project_id: str) -> list[dict]:
        return await self.find({"project_id": project_id, "deleted": {"$ne": True}})

    async def soft_delete(self, file_id: str, deleted_by: str) -> bool:
        from datetime import datetime
        return await self.update(file_id, {
            "deleted": True,
            "deleted_at": datetime.utcnow(),
            "deleted_by": deleted_by,
        })
