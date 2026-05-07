from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from backend.core.config import settings

_client: AsyncIOMotorClient | None = None


async def get_database() -> AsyncIOMotorDatabase:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongodb_url)
    return _client[settings.mongodb_db_name]


async def close_database():
    global _client
    if _client is not None:
        _client.close()
        _client = None
