"""Pipeline executor: runs the LangGraph pipeline with Redis-backed checkpointing and HITL pause/resume."""
import asyncio
import json
import logging
import time

import redis.asyncio as redis

from backend.core.config import settings
from backend.core.database.connection import get_database
from backend.core.database.repositories.proposal_versions import ProposalVersionRepository
from backend.core.database.repositories.stage_metrics import StageMetricsRepository
from backend.core.graph.state import BudgetExceeded, RequestBudget

logger = logging.getLogger(__name__)

HITL_NODES = {"hitl_brief", "hitl_strategy", "hitl_structure", "hitl_gallery"}


class PipelineExecutor:
    def __init__(self, pipeline_id: str):
        self.pipeline_id = pipeline_id
        self.redis = redis.from_url(settings.redis_url)
        self._state_key = f"pipeline:{pipeline_id}:state"
        self._status_key = f"pipeline:{pipeline_id}:status"
        self._resume_event_key = f"pipeline:{pipeline_id}:resume"

    async def save_state(self, state: dict):
        await self.redis.set(
            self._state_key,
            json.dumps(state, default=str),
            ex=86400,
        )

    async def load_state(self) -> dict | None:
        data = await self.redis.get(self._state_key)
        if data:
            return json.loads(data)
        return None

    async def set_status(self, status: str, node: str | None = None):
        info = {"status": status, "current_node": node, "updated_at": time.time()}
        await self.redis.set(self._status_key, json.dumps(info), ex=86400)

    async def get_status(self) -> dict:
        data = await self.redis.get(self._status_key)
        if data:
            return json.loads(data)
        return {"status": "unknown", "current_node": None}

    async def wait_for_resume(self, timeout: float = 3600) -> dict:
        """Block until user sends HITL response via Redis pubsub."""
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(self._resume_event_key)
        try:
            deadline = time.time() + timeout
            async for message in pubsub.listen():
                if message["type"] == "message":
                    return json.loads(message["data"])
                if time.time() > deadline:
                    return {"action": "timeout"}
        finally:
            await pubsub.unsubscribe(self._resume_event_key)

    async def resume(self, data: dict):
        """Called by WebSocket/API handler to resume a paused pipeline."""
        await self.redis.publish(
            self._resume_event_key,
            json.dumps(data),
        )

    async def run(self, initial_state: dict, start_from: str | None = None):
        """Execute the full pipeline with HITL checkpoints. Optionally start from a specific node (rerun)."""
        from backend.core.graph.pipeline import (
            brand_check_node,
            brief_analyzer_node,
            deck_orchestrator_node,
            narrative_agent_node,
            ppt_builder_node,
            research_agent_node,
            resource_agent_node,
            slide_content_node,
            strategy_phase1_node,
            strategy_phase2_node,
        )

        state = initial_state.copy()
        state.setdefault("request_budget", RequestBudget())

        node_sequence = [
            ("brief_analyzer", brief_analyzer_node),
            ("hitl_brief", None),
            ("parallel_research_strategy", None),
            ("strategy_phase2", strategy_phase2_node),
            ("brand_check", brand_check_node),
            ("hitl_strategy", None),
            ("resource_agent", resource_agent_node),
            ("deck_orchestrator", deck_orchestrator_node),
            ("hitl_structure", None),
            ("slide_content", slide_content_node),
            ("narrative_agent", narrative_agent_node),
            ("hitl_gallery", None),
            ("ppt_builder", ppt_builder_node),
        ]

        # Skip nodes before start_from for rerun
        if start_from:
            node_names = [n[0] for n in node_sequence]
            if start_from in node_names:
                start_idx = node_names.index(start_from)
                node_sequence = node_sequence[start_idx:]

        metrics = {}

        try:
            for node_name, node_fn in node_sequence:
                await self.set_status("running", node_name)
                await self.save_state(state)
                await self._notify_node_entered(node_name)

                if node_name in HITL_NODES:
                    await self._notify_hitl_required(node_name, state)
                    await self.set_status("paused", node_name)
                    response = await self.wait_for_resume()
                    state = self._apply_hitl_response(state, node_name, response)

                elif node_name == "parallel_research_strategy":
                    t0 = time.time()
                    research_task = asyncio.create_task(research_agent_node(state))
                    strategy_task = asyncio.create_task(strategy_phase1_node(state))
                    research_result, strategy_result = await asyncio.gather(
                        research_task, strategy_task
                    )
                    state.update(research_result)
                    state.update(strategy_result)
                    metrics["research_agent"] = {"duration_s": round(time.time() - t0, 1)}

                elif node_fn:
                    t0 = time.time()
                    result = await node_fn(state)
                    state.update(result)
                    duration = round(time.time() - t0, 1)
                    metrics[node_name] = {"duration_s": duration}

                    if node_name == "slide_content":
                        await self._stream_slides(state)

            await self.set_status("completed", "ppt_builder")
            await self.save_state(state)
            await self._notify_complete(state.get("pptx_path", ""))

            await self._save_metrics(state, metrics)

            trigger = "rerun" if start_from else "pipeline_complete"
            await self._save_version(state, trigger=trigger)
            await self._accumulate_resource_tags(state)

        except BudgetExceeded as e:
            await self.set_status("budget_exceeded", None)
            logger.warning(f"Pipeline {self.pipeline_id} budget exceeded: {e}")
        except Exception as e:
            await self.set_status("error", None)
            logger.error(f"Pipeline {self.pipeline_id} failed: {e}", exc_info=True)

    def _apply_hitl_response(self, state: dict, node: str, response: dict) -> dict:
        action = response.get("action", "confirm")

        if action == "rerun":
            state["rerun_from"] = response.get("rerun_from", "")
            return state

        if node == "hitl_brief":
            state["brief_confirmed"] = True
            if response.get("edits"):
                state.setdefault("structured_brief", {}).update(response["edits"])
        elif node == "hitl_strategy":
            if action == "confirm":
                state["strategy_confirmed"] = True
            else:
                state["strategy_feedback"] = response.get("feedback", "")
                state["rerun_refresh_research"] = response.get("refresh_research", False)
        elif node == "hitl_structure":
            state["structure_confirmed"] = True
            if response.get("edits") and "deck_structure" in response["edits"]:
                state["deck_structure"] = response["edits"]["deck_structure"]
        elif node == "hitl_gallery":
            state["slides_confirmed"] = True
            flagged = response.get("flagged_indices", [])
            for idx in flagged:
                if idx < len(state.get("slides", [])):
                    state["slides"][idx]["status"] = "flagged"
                    state["slides"][idx]["feedback"] = response.get("feedback", "")
        return state

    async def _notify_node_entered(self, node: str):
        from backend.api.v1.websocket import manager
        await manager.broadcast_node_entered(self.pipeline_id, node)

    async def _notify_hitl_required(self, node: str, state: dict):
        from backend.api.v1.websocket import manager
        data = {}
        if node == "hitl_brief":
            data = {"structured_brief": state.get("structured_brief", {})}
        elif node == "hitl_strategy":
            data = {
                "strategy_result": state.get("strategy_result", {}),
                "research_result": state.get("research_result", {}),
                "brand_check_passed": state.get("brand_check_passed"),
            }
        elif node == "hitl_structure":
            data = {"deck_structure": state.get("deck_structure", [])}
        elif node == "hitl_gallery":
            data = {
                "slides": state.get("slides", []),
                "narrative_suggestions": state.get("narrative_suggestions", []),
            }
        await manager.broadcast_hitl_required(self.pipeline_id, node, data)

    async def _stream_slides(self, state: dict):
        from backend.api.v1.websocket import manager
        for slide in state.get("slides", []):
            await manager.broadcast_slide_generated(
                self.pipeline_id, slide["index"], slide["content"]
            )

    async def _notify_complete(self, pptx_path: str):
        from backend.api.v1.websocket import manager
        await manager.broadcast_pipeline_complete(self.pipeline_id, pptx_path)

    async def _save_version(self, state: dict, trigger: str = "pipeline_complete"):
        db = await get_database()
        repo = ProposalVersionRepository(db)
        proposal_id = state.get("proposal_id", self.pipeline_id)
        await repo.save_version(proposal_id, state, trigger=trigger)

    async def _save_metrics(self, state: dict, metrics: dict):
        db = await get_database()
        repo = StageMetricsRepository(db)

        budget = state.get("request_budget")
        if isinstance(budget, RequestBudget):
            metrics["request_budget"] = {
                "llm_calls_used": budget.current_llm_calls,
                "search_calls_used": budget.current_search_calls,
                "total_seconds": round(time.time() - budget.start_time, 1),
            }

        await repo.create({
            "proposal_id": state.get("proposal_id", ""),
            "project_id": state.get("project_id", ""),
            "client_id": state.get("client_id", ""),
            **metrics,
        })

    async def _accumulate_resource_tags(self, state: dict):
        """Post-pipeline: tag selected resources with project category for progressive profiling."""
        resource_result = state.get("resource_result", {})
        if not resource_result or resource_result.get("skipped"):
            return

        brief = state.get("structured_brief", {})
        category = brief.get("category", "")
        if not category or category == "not provided":
            return

        client_id = state.get("client_id", "")
        if not client_id:
            return

        recommended = resource_result.get("recommended_resources", [])
        if not recommended:
            return

        try:
            db = await get_database()
            collection = db["resources"]

            for rec in recommended:
                name = rec.get("name", "") if isinstance(rec, dict) else ""
                if not name:
                    continue
                await collection.update_one(
                    {
                        "client_id": client_id,
                        "name": {"$regex": f"^{name}$", "$options": "i"},
                    },
                    {"$addToSet": {"categories": category}},
                )
        except Exception as e:
            logger.warning(f"Resource accumulation failed: {e}")
