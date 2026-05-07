from backend.core.database.repositories.base import BaseRepository


class FeedbackRepository(BaseRepository):
    collection_name = "feedback"

    async def find_by_client(self, client_id: str) -> list[dict]:
        return await self.find({"client_id": client_id})

    async def find_rejected_directions(self, client_id: str) -> list[str]:
        docs = await self.find({"client_id": client_id, "rejected_directions": {"$ne": []}})
        directions = []
        for doc in docs:
            directions.extend(doc.get("rejected_directions", []))
        return directions
