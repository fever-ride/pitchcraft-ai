from backend.core.database.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    collection_name = "users"

    async def find_by_email(self, email: str) -> dict | None:
        doc = await self.collection.find_one({"email": email})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def find_by_oauth(self, provider: str, oauth_id: str) -> dict | None:
        doc = await self.collection.find_one(
            {"oauth_provider": provider, "oauth_id": oauth_id}
        )
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def find_by_organization(self, organization_id: str) -> list[dict]:
        return await self.find({"organization_id": organization_id})
