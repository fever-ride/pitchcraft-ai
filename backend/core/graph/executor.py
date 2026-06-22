"""Pipeline executor: runs the LangGraph pipeline with Redis-backed checkpointing and HITL pause/resume.

Architecture (Option B — stateless per-request execution):

  AsyncRedisSaver (LangGraph checkpoint)
    • Persists LangGraph execution checkpoints to Redis.
    • Survives process restarts; enables HITL resume across separate HTTP requests.
    • Thread ID = pipeline_id, consistent across all start() / resume_pipeline() calls.

  Redis app state  (pipeline:{id}:state)
    • Human-readable dict snapshot for frontend GET endpoints.
    • Updated after every non-HITL node in _stream_run.
    • RequestBudget excluded: non-serializable; recreated fresh each call.
    • Authoritative for: current proposal output, frontend data reads, rerun seeding.

  Redis timings    (pipeline:{id}:timings)
    • Accumulated per-node wall-clock timings across all execution segments.
    • Saved at the end of each segment; loaded at the start of resume_pipeline().

HITL flow (stateless, no long-lived coroutine, no pub/sub):
  POST /pipeline/start         → start(initial_state)
                                   → graph runs until first interrupt → background task ends
  POST /pipeline/{id}/confirm  → resume_pipeline(response)
                                   → graph resumes from checkpoint until next interrupt → ends
  Between calls the full LangGraph state is preserved in AsyncRedisSaver (Redis).

Rerun flow:
  External rerun (POST /pipeline/{id}/rerun):
    → start(state, start_from=node)
    → _prime_checkpointer_for_rerun → astream(None) from node

  Inline rerun (hitl_strategy action="rerun"):
    → hitl_strategy_node returns {"rerun_from": "..."}
    → _stream_run detects it early, returns the node name
    → _run_until_interrupt_or_done loops: prime + restream
"""
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

# Maps each node to the direct predecessor(s) that must be simulated via aupdate_state
# so that graph.astream(None, config) starts at that node.
# Fan-in nodes (strategy_phase2) need multiple predecessors simulated.
_RERUN_PREDECESSORS: dict[str, list[str]] = {
    "brief_analyzer": [],                                       # entry node
    "hitl_brief": ["brief_analyzer"],
    "research_agent": ["hitl_brief"],
    "strategy_phase1": ["hitl_brief"],
    "strategy_phase2": ["research_agent", "strategy_phase1"],  # fan-in
    "brand_check": ["strategy_phase2"],
    "hitl_strategy": ["brand_check"],
    "media_planner": ["hitl_strategy"],
    "hitl_media": ["media_planner"],
    "resource_agent": ["hitl_media"],
    "deck_orchestrator": ["resource_agent"],
    "hitl_structure": ["deck_orchestrator"],
    "slide_content": ["hitl_structure"],
    "narrative_agent": ["slide_content"],
    "hitl_gallery": ["narrative_agent"],
    "ppt_builder": ["hitl_gallery"],
}


class PipelineExecutor:
    def __init__(self, pipeline_id: str):
        self.pipeline_id = pipeline_id
        self.redis = redis.from_url(settings.redis_url)
        self._state_key = f"pipeline:{pipeline_id}:state"
        self._status_key = f"pipeline:{pipeline_id}:status"
        self._timings_key = f"pipeline:{pipeline_id}:timings"

    # ------------------------------------------------------------------
    # Redis app state helpers
    # ------------------------------------------------------------------

    async def save_state(self, state: dict):
        """Persist human-readable proposal state to Redis (strips RequestBudget)."""
        serializable = {k: v for k, v in state.items() if k != "request_budget"}
        await self.redis.set(
            self._state_key,
            json.dumps(serializable, default=str),
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

    async def _load_timings(self) -> dict[str, float]:
        data = await self.redis.get(self._timings_key)
        if data:
            return json.loads(data)
        return {}

    async def _save_timings(self, timings: dict[str, float]):
        await self.redis.set(self._timings_key, json.dumps(timings), ex=86400)

    # ------------------------------------------------------------------
    # Public execution API
    # ------------------------------------------------------------------

    async def start(self, initial_state: dict, start_from: str | None = None):
        """Start pipeline from the beginning, or restart from a specific node.

        Runs until the first HITL interrupt (or completion), then returns.
        Designed to be called as a short-lived FastAPI BackgroundTask.

        start_from: if set, loads the latest Redis app state and restarts natively
                    from that node using the LangGraph checkpointer.
        """
        from langgraph_checkpoint_redis import AsyncRedisSaver
        from backend.core.graph.pipeline import build_compiled_pipeline

        async with AsyncRedisSaver.from_conn_string(settings.redis_url) as checkpointer:
            graph = build_compiled_pipeline(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": self.pipeline_id}}
            node_timings: dict[str, float] = {}

            if start_from:
                # External rerun: merge Redis state with any overrides from initial_state
                saved = await self.load_state() or {}
                rerun_state = {**saved, **{k: v for k, v in initial_state.items() if v is not None}}
                rerun_state.pop("rerun_from", None)
                if not isinstance(rerun_state.get("request_budget"), RequestBudget):
                    rerun_state["request_budget"] = RequestBudget()
                await self.set_status("running", start_from)
                await self._prime_checkpointer_for_rerun(graph, config, rerun_state, start_from)
                input_ = None   # astream(None) resumes from primed checkpoint
            else:
                state = initial_state.copy()
                if not isinstance(state.get("request_budget"), RequestBudget):
                    state["request_budget"] = RequestBudget()
                await self.set_status("running", "brief_analyzer")
                input_ = state

            try:
                await self._run_until_interrupt_or_done(
                    graph, input_, config, node_timings,
                    is_rerun=(start_from is not None),
                )
            except BudgetExceeded as e:
                await self.set_status("budget_exceeded", None)
                logger.warning(f"Pipeline {self.pipeline_id} budget exceeded: {e}")
            except Exception as e:
                await self.set_status("error", None)
                logger.error(f"Pipeline {self.pipeline_id} failed: {e}", exc_info=True)

    async def resume_pipeline(self, response: dict):
        """Resume pipeline from a HITL interrupt with the user's response.

        Loads the LangGraph checkpoint from AsyncRedisSaver, feeds the response via
        Command(resume=response), and runs until the next HITL interrupt (or completion),
        then returns.
        Designed to be called as a short-lived FastAPI BackgroundTask.
        """
        from langgraph.types import Command
        from langgraph_checkpoint_redis import AsyncRedisSaver
        from backend.core.graph.pipeline import build_compiled_pipeline

        async with AsyncRedisSaver.from_conn_string(settings.redis_url) as checkpointer:
            graph = build_compiled_pipeline(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": self.pipeline_id}}

            # Restore accumulated node timings from previous execution segments
            node_timings = await self._load_timings()

            status = await self.get_status()
            interrupted_node = status.get("current_node")
            await self.set_status("running", interrupted_node)

            try:
                await self._run_until_interrupt_or_done(
                    graph, Command(resume=response), config, node_timings, is_rerun=False,
                )
            except BudgetExceeded as e:
                await self.set_status("budget_exceeded", None)
                logger.warning(f"Pipeline {self.pipeline_id} budget exceeded: {e}")
            except Exception as e:
                await self.set_status("error", None)
                logger.error(f"Pipeline {self.pipeline_id} failed: {e}", exc_info=True)

    # ------------------------------------------------------------------
    # Internal execution helpers
    # ------------------------------------------------------------------

    async def _run_until_interrupt_or_done(
        self,
        graph,
        input_,
        config: dict,
        node_timings: dict[str, float],
        is_rerun: bool,
    ):
        """Stream the graph until the next HITL interrupt or pipeline completion.

        Handles inline reruns (hitl_strategy action="rerun") via an internal loop.
        Persists node timings after each segment so resume_pipeline() can accumulate them.
        """
        inline_rerun = await self._stream_run(graph, input_, config, node_timings)

        # Inline rerun loop: hitl_strategy_node returned {"rerun_from": "..."} for action="rerun"
        while inline_rerun:
            current_state = dict((await graph.aget_state(config)).values)
            current_state.pop("rerun_from", None)
            if not isinstance(current_state.get("request_budget"), RequestBudget):
                current_state["request_budget"] = RequestBudget()
            logger.info(f"[{self.pipeline_id}] Inline rerun from '{inline_rerun}'")
            await self.set_status("running", inline_rerun)
            await self._prime_checkpointer_for_rerun(graph, config, current_state, inline_rerun)
            inline_rerun = await self._stream_run(graph, None, config, node_timings)

        # Persist timings so the next resume_pipeline() call can accumulate them
        await self._save_timings(node_timings)

        snapshot = await graph.aget_state(config)
        if snapshot.next:
            # Graph is paused at a HITL interrupt — wait for resume_pipeline()
            interrupted_node = snapshot.next[0]
            interrupt_data = {}
            for task in snapshot.tasks:
                if task.interrupts:
                    interrupt_data = task.interrupts[0].value
                    break
            await self.set_status("paused", interrupted_node)
            await self.save_state(dict(snapshot.values))
            await self._notify_hitl_required(interrupted_node, interrupt_data)
        else:
            # Pipeline complete
            final_state = dict(snapshot.values)
            await self.set_status("completed", "ppt_builder")
            await self.save_state(final_state)
            await self._notify_complete(final_state.get("pptx_path", ""))
            await self._save_metrics(final_state, {"node_timings": node_timings})
            trigger = "rerun" if is_rerun else "pipeline_complete"
            await self._save_version(final_state, trigger=trigger)
            await self._accumulate_resource_tags(final_state)

    async def _prime_checkpointer_for_rerun(
        self, graph, config: dict, state: dict, rerun_from: str
    ) -> None:
        """Prime the checkpointer so that astream(None, config) starts at rerun_from.

        Simulates each direct predecessor of rerun_from having "run" via aupdate_state,
        which tells LangGraph that those nodes completed and rerun_from is next.
        For fan-in nodes (strategy_phase2), both predecessors are simulated.

        RequestBudget is stripped from the primed state since it is not JSON-safe
        and is recreated fresh at the top of each start() call.
        """
        state_to_prime = {k: v for k, v in state.items() if k != "request_budget"}

        predecessors = _RERUN_PREDECESSORS.get(rerun_from)
        if predecessors is None:
            logger.warning(
                f"[{self.pipeline_id}] Unknown rerun_from='{rerun_from}'; "
                "priming at entry point (brief_analyzer)"
            )
            await graph.aupdate_state(config, state_to_prime)
            return

        if not predecessors:
            # Entry node — just set the initial state
            await graph.aupdate_state(config, state_to_prime)
        else:
            for pred in predecessors:
                await graph.aupdate_state(config, state_to_prime, as_node=pred)

    async def _stream_run(
        self,
        graph,
        input_or_command,
        config,
        node_timings: dict | None = None,
    ) -> str | None:
        """Stream graph execution until next interrupt, inline rerun signal, or completion.

        Returns the rerun_from node name if a node signals an inline rerun
        (e.g. hitl_strategy_node returning {"rerun_from": "..."}), otherwise None.

        Side effects:
          - Saves Redis app state after each non-HITL node (continuous crash recovery).
          - Records per-node wall-clock timing in node_timings.
          - Notifies WebSocket clients of node progress and slide generation.
        """
        _last_event_time = time.time()
        async for event in graph.astream(input_or_command, config=config, stream_mode="updates"):
            if "__interrupt__" in event:
                break  # Graph paused at a HITL interrupt

            for node_name, updates in event.items():
                if node_name.startswith("__"):
                    continue

                # Detect inline rerun signal — break BEFORE any downstream nodes run.
                if isinstance(updates, dict) and updates.get("rerun_from"):
                    return updates["rerun_from"]

                now = time.time()
                if node_timings is not None:
                    node_timings[node_name] = round(now - _last_event_time, 2)
                _last_event_time = now

                await self._notify_node_entered(node_name)

                # Save Redis snapshot after each non-HITL node so Redis always mirrors
                # LangGraph execution state (not just at HITL pauses).
                if not node_name.startswith("hitl_"):
                    snapshot = await graph.aget_state(config)
                    snap_dict = dict(snapshot.values)
                    await self.save_state(snap_dict)
                    if node_name == "slide_content":
                        await self._stream_slides(snap_dict)

        return None

    # ------------------------------------------------------------------
    # Notification helpers
    # ------------------------------------------------------------------

    async def _notify_node_entered(self, node: str):
        from backend.api.v1.websocket import manager
        await manager.broadcast_node_entered(self.pipeline_id, node)

    async def _notify_hitl_required(self, node: str, interrupt_data: dict):
        from backend.api.v1.websocket import manager
        await manager.broadcast_hitl_required(self.pipeline_id, node, interrupt_data)

    async def _stream_slides(self, state: dict):
        from backend.api.v1.websocket import manager
        for slide in state.get("slides", []):
            await manager.broadcast_slide_generated(
                self.pipeline_id, slide["index"], slide["content"]
            )

    async def _notify_complete(self, pptx_path: str):
        from backend.api.v1.websocket import manager
        await manager.broadcast_pipeline_complete(self.pipeline_id, pptx_path)

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

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
        org_id = state.get("org_id", "")

        recommended = resource_result.get("recommended_resources", [])
        if not recommended:
            return

        try:
            from backend.core.database.repositories.resources import ResourceRepository
            from backend.core.rag.resource_import import refresh_resource_embedding
            db = await get_database()
            repo = ResourceRepository(db)

            for rec in recommended:
                name = rec.get("name", "") if isinstance(rec, dict) else ""
                if not name:
                    continue
                updated_doc = await repo.add_category_tag(
                    org_id=org_id, name=name, category=category, client_id=client_id
                )
                if updated_doc:
                    await refresh_resource_embedding(updated_doc)
        except Exception as e:
            logger.warning(f"Resource accumulation failed: {e}")
