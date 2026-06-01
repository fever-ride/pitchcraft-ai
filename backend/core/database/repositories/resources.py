from datetime import datetime

from bson import ObjectId

from backend.core.database.repositories.base import BaseRepository


class ResourceRepository(BaseRepository):
    collection_name = "resources"

    # --- Existing (kept for backward compat) ---

    async def find_by_type(self, resource_type: str) -> list[dict]:
        return await self.find({"type": resource_type})

    async def find_by_tags(self, resource_type: str, tags: list[str]) -> list[dict]:
        return await self.find({
            "type": resource_type,
            "tags": {"$in": tags},
        })

    # --- New ---

    async def find_by_name(self, client_id: str, name: str) -> dict | None:
        """Case-insensitive exact name match within a client's resource pool."""
        doc = await self.collection.find_one({
            "client_id": client_id,
            "name": {"$regex": f"^{name}$", "$options": "i"},
        })
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def find_filtered(
        self,
        client_id: str,
        type: str | None = None,
        status_filter: str | None = None,
        min_followers: int | None = None,
        limit: int = 200,
    ) -> list[dict]:
        """List resources with optional type / status / follower-count filters."""
        from backend.core.models.resource import ResourceStatus

        query: dict = {"client_id": client_id}
        if type:
            query["type"] = type
        if status_filter:
            query["status"] = status_filter
        else:
            query["status"] = {"$ne": ResourceStatus.INACTIVE.value}
        if min_followers is not None:
            query["followers_count"] = {"$gte": min_followers}

        cursor = self.collection.find(query).limit(limit)
        docs = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            docs.append(doc)
        return docs

    async def add_category_tag(
        self,
        client_id: str,
        name: str,
        category: str,
    ) -> dict | None:
        """Add a category tag via $addToSet and return the updated document.

        Used by the progressive accumulation step after pipeline completion.
        Returns None if no matching resource is found.
        """
        await self.collection.update_one(
            {"client_id": client_id, "name": {"$regex": f"^{name}$", "$options": "i"}},
            {"$addToSet": {"categories": category}},
        )
        return await self.find_by_name(client_id, name)

    async def add_collaboration_record(self, resource_id: str, record: dict) -> None:
        """Append a collaboration/performance record to collaboration_history via $push."""
        await self.collection.update_one(
            {"_id": ObjectId(resource_id)},
            {"$push": {"collaboration_history": record}},
        )

    async def verify(self, resource_id: str) -> bool:
        """Mark a resource as freshly verified (sets last_verified_at to now)."""
        return await self.update(resource_id, {"last_verified_at": datetime.utcnow()})

    async def update_status(self, resource_id: str, new_status: str) -> bool:
        """Update active/inactive status."""
        return await self.update(resource_id, {"status": new_status})
