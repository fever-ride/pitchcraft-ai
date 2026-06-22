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

    def _pool_query(
        self,
        org_id: str = "",
        client_id: str = "",
        scope: str = "",
    ) -> dict:
        """Build the pool-isolation part of a MongoDB query.

        scope=""       + org_id + client_id  → shared + client combined
        scope="shared" + org_id              → agency-wide pool only
        scope="client" + client_id           → client-specific pool only
        client_id only (no org_id, backward compat) → client_id match
        """
        if scope == "shared" and org_id:
            return {"org_id": org_id, "scope": "shared"}
        if scope == "client" and client_id:
            return {"client_id": client_id}
        if org_id and client_id:
            # Both pools
            return {"$or": [
                {"org_id": org_id, "scope": "shared"},
                {"client_id": client_id},
            ]}
        if org_id:
            return {"org_id": org_id, "scope": "shared"}
        if client_id:
            return {"client_id": client_id}   # backward compat
        return {}

    async def get_names_set(
        self,
        client_id: str = "",
        org_id: str = "",
        scope: str = "client",
    ) -> set[str]:
        """Return lowercase set of resource names for dedup during import."""
        query = self._pool_query(org_id=org_id, client_id=client_id, scope=scope)
        if not query:
            return set()
        cursor = self.collection.find(query, {"name": 1})
        return {doc["name"].lower() async for doc in cursor}

    async def find_by_name(
        self,
        org_id: str,
        name: str,
        client_id: str = "",
        scope: str = "",
    ) -> dict | None:
        """Case-insensitive exact name match.

        scope=""  → searches shared + client pools (useful for agent validation).
        scope="shared" → shared pool only.
        scope="client" → client-specific pool only.
        """
        pool_q = self._pool_query(org_id=org_id, client_id=client_id, scope=scope)
        name_filter = {"name": {"$regex": f"^{name}$", "$options": "i"}}
        query = {**pool_q, **name_filter} if "$or" not in pool_q else {
            "$and": [pool_q, name_filter]
        }
        doc = await self.collection.find_one(query)
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def find_filtered(
        self,
        client_id: str = "",
        org_id: str = "",
        scope: str = "",           # "shared" | "client" | "" (both)
        type: str | None = None,
        status_filter: str | None = None,
        min_followers: int | None = None,
        limit: int = 200,
    ) -> list[dict]:
        """List resources with optional type / status / follower-count filters."""
        from backend.core.models.resource import ResourceStatus

        pool_q = self._pool_query(org_id=org_id, client_id=client_id, scope=scope)
        query: dict = dict(pool_q)  # shallow copy

        if type:
            query["type"] = type
        if status_filter:
            query["status"] = status_filter
        else:
            query["status"] = {"$ne": ResourceStatus.INACTIVE.value}
        if min_followers is not None:
            query["total_followers_count"] = {"$gte": min_followers}

        cursor = self.collection.find(query).limit(limit)
        docs = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            docs.append(doc)
        return docs

    async def add_category_tag(
        self,
        org_id: str,
        name: str,
        category: str,
        client_id: str = "",
    ) -> dict | None:
        """Add a category tag via $addToSet and return the updated document.

        Used by the progressive accumulation step after pipeline completion.
        Returns None if no matching resource is found.
        """
        pool_q = self._pool_query(org_id=org_id, client_id=client_id, scope="")
        name_filter = {"name": {"$regex": f"^{name}$", "$options": "i"}}
        query = {**pool_q, **name_filter} if "$or" not in pool_q else {
            "$and": [pool_q, name_filter]
        }
        await self.collection.update_one(
            query,
            {"$addToSet": {"categories": category}},
        )
        return await self.find_by_name(org_id=org_id, name=name, client_id=client_id, scope="")

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
