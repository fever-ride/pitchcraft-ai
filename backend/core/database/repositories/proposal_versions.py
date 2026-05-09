from datetime import datetime

from backend.core.database.repositories.base import BaseRepository


class ProposalVersionRepository(BaseRepository):
    collection_name = "proposal_versions"

    async def find_by_proposal(self, proposal_id: str) -> list[dict]:
        return await self.find(
            {"proposal_id": proposal_id},
            limit=100,
        )

    async def get_version(self, proposal_id: str, version: int) -> dict | None:
        doc = await self.collection.find_one(
            {"proposal_id": proposal_id, "version": version}
        )
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def get_latest(self, proposal_id: str) -> dict | None:
        doc = await self.collection.find_one(
            {"proposal_id": proposal_id},
            sort=[("version", -1)],
        )
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def get_latest_version_number(self, proposal_id: str) -> int:
        doc = await self.collection.find_one(
            {"proposal_id": proposal_id},
            sort=[("version", -1)],
            projection={"version": 1},
        )
        return doc["version"] if doc else 0

    async def save_version(
        self,
        proposal_id: str,
        state: dict,
        trigger: str = "pipeline_complete",
        note: str = "",
    ) -> int:
        next_version = await self.get_latest_version_number(proposal_id) + 1

        snapshot = {
            "structured_brief": state.get("structured_brief"),
            "research_result": state.get("research_result"),
            "strategy_result": state.get("strategy_result"),
            "deck_structure": state.get("deck_structure"),
            "slides": state.get("slides"),
            "pptx_path": state.get("pptx_path"),
            "resource_result": state.get("resource_result"),
            "narrative_suggestions": state.get("narrative_suggestions"),
        }

        await self.create({
            "proposal_id": proposal_id,
            "project_id": state.get("project_id", ""),
            "client_id": state.get("client_id", ""),
            "version": next_version,
            "trigger": trigger,
            "note": note,
            "snapshot": snapshot,
            "created_at": datetime.utcnow(),
        })

        return next_version
