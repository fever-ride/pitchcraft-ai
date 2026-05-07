import json
import time

import redis.asyncio as redis

from backend.core.config import settings


class SemanticCache:
    def __init__(self):
        self.redis = redis.from_url(settings.redis_url)
        self.ttl_days = 30

    def _make_key(self, client_id: str, competitor_name: str) -> str:
        date_bucket = int(time.time()) // (30 * 86400)
        return f"research:{client_id}:{competitor_name}:{date_bucket}"

    async def get(self, client_id: str, competitor_name: str) -> dict | None:
        key = self._make_key(client_id, competitor_name)
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None

    async def set(self, client_id: str, competitor_name: str, result: dict):
        key = self._make_key(client_id, competitor_name)
        await self.redis.setex(
            key,
            self.ttl_days * 86400,
            json.dumps(result, ensure_ascii=False),
        )

    async def invalidate(self, client_id: str, competitor_name: str):
        key = self._make_key(client_id, competitor_name)
        await self.redis.delete(key)
