from backend.core.database.repositories.base import BaseRepository


class ProjectRepository(BaseRepository):
    collection_name = "projects"

    async def find_by_client(self, client_id: str) -> list[dict]:
        return await self.find({"client_id": client_id})

    async def find_accessible(self, client_id: str, user_id: str) -> list[dict]:
        return await self.find({
            "client_id": client_id,
            "$or": [
                {"assigned_accounts": user_id},
                {"assigned_accounts": {"$size": 0}},
            ],
        })
