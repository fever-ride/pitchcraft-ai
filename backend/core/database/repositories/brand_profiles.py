from datetime import datetime

from backend.core.database.repositories.base import BaseRepository


class BrandProfileRepository(BaseRepository):
    collection_name = "brand_profiles"

    async def find_by_client(self, client_id: str) -> dict | None:
        doc = await self.collection.find_one({"client_id": client_id})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def upsert_by_client(self, client_id: str, data: dict) -> str:
        data["updated_at"] = datetime.utcnow()
        result = await self.collection.update_one(
            {"client_id": client_id},
            {"$set": data, "$setOnInsert": {"created_at": datetime.utcnow()}},
            upsert=True,
        )
        if result.upserted_id is not None:
            return str(result.upserted_id)
        doc = await self.collection.find_one({"client_id": client_id}, {"_id": 1})
        return str(doc["_id"]) if doc else ""

    async def add_feedback_directions(
        self,
        client_id: str,
        approved: list[str] | None = None,
        rejected: list[str] | None = None,
    ) -> None:
        """Append new approved/rejected directions from feedback into the profile.

        Uses $addToSet so duplicates are never stored.
        No-op if no BrandProfile exists for this client yet — the AE must
        create the profile first; feedback then enriches it incrementally.
        """
        add_to_set: dict = {}
        if approved:
            add_to_set["approved_directions"] = {"$each": approved}
        if rejected:
            add_to_set["rejected_directions"] = {"$each": rejected}
        if not add_to_set:
            return

        await self.collection.update_one(
            {"client_id": client_id},
            {
                "$addToSet": add_to_set,
                "$set": {"updated_at": datetime.utcnow()},
            },
            # No upsert — only enrich an existing profile
        )
