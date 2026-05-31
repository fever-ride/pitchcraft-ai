"""Repository for persisting Research Agent results.

Replaces the Redis SemanticCache. Results are keyed by (client_id, brief_hash)
so the same brief within 30 days reuses the stored result instead of re-running
web searches. The user can always override via force_refresh=True.

Suggested index (run once in Atlas or migration):
  db.research_results.createIndex(
      { client_id: 1, brief_hash: 1, created_at: -1 }
  )
"""
from datetime import datetime, timedelta

from backend.core.database.repositories.base import BaseRepository


class ResearchResultRepository(BaseRepository):
    collection_name = "research_results"

    async def save_result(
        self,
        client_id: str,
        org_id: str,
        brief_hash: str,
        result: dict,
        queries_used: list[str],
    ) -> str:
        """Persist a new research result. Does not upsert — keeps full history."""
        data = {
            "client_id": client_id,
            "org_id": org_id,
            "brief_hash": brief_hash,
            "result": result,
            "queries_used": queries_used,
            "created_at": datetime.utcnow(),
        }
        return await self.create(data)

    async def find_recent(
        self,
        client_id: str,
        brief_hash: str,
        max_age_days: int = 30,
    ) -> dict | None:
        """Return the most recent result for this client + brief within max_age_days.

        Returns None if no match or all matches are too old.
        """
        cutoff = datetime.utcnow() - timedelta(days=max_age_days)
        doc = await self.collection.find_one(
            {
                "client_id": client_id,
                "brief_hash": brief_hash,
                "created_at": {"$gte": cutoff},
            },
            sort=[("created_at", -1)],
        )
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def find_by_client(
        self,
        client_id: str,
        limit: int = 10,
    ) -> list[dict]:
        """Return recent research history for a client (newest first)."""
        cursor = (
            self.collection.find({"client_id": client_id})
            .sort("created_at", -1)
            .limit(limit)
        )
        docs = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            # Exclude the full result blob for list views — callers can fetch by _id
            doc.pop("result", None)
            docs.append(doc)
        return docs
