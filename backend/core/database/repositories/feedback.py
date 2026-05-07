from backend.core.database.repositories.base import BaseRepository


class FeedbackRepository(BaseRepository):
    collection_name = "feedback"

    async def find_by_client(self, client_id: str, limit: int = 50) -> list[dict]:
        return await self.find({"client_id": client_id}, limit=limit)

    async def find_by_project(self, project_id: str, limit: int = 50) -> list[dict]:
        return await self.find({"project_id": project_id}, limit=limit)

    async def find_rejected_directions(self, client_id: str) -> list[str]:
        docs = await self.find({"client_id": client_id, "rejected_directions": {"$ne": []}})
        directions = []
        for doc in docs:
            directions.extend(doc.get("rejected_directions", []))
        return directions

    async def find_approved_directions(self, client_id: str) -> list[str]:
        docs = await self.find({"client_id": client_id, "approved_directions": {"$ne": []}})
        directions = []
        for doc in docs:
            directions.extend(doc.get("approved_directions", []))
        return directions

    async def find_unembedded(self, limit: int = 100) -> list[dict]:
        return await self.find({"embedded": False, "approved_directions": {"$ne": []}}, limit=limit)

    async def mark_embedded(self, feedback_id: str) -> bool:
        return await self.update(feedback_id, {"embedded": True})
