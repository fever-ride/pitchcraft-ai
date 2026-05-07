from backend.core.database.repositories.base import BaseRepository


class ClientRepository(BaseRepository):
    collection_name = "clients"

    async def find_by_organization(self, organization_id: str) -> list[dict]:
        return await self.find({"organization_id": organization_id})
