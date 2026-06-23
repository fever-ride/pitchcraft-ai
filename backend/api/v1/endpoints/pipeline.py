import time
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel

from backend.api.v1.permissions import CurrentUser, get_current_user
from backend.core.graph.executor import PipelineExecutor

router = APIRouter()


async def _require_owner(executor: PipelineExecutor, user: CurrentUser) -> dict:
    """Load pipeline state and verify the requesting user's org owns this pipeline.

    Raises 404 if the pipeline doesn't exist, 403 if the org doesn't match.
    Returns the loaded state so callers don't need a second load_state() call.
    """
    state = await executor.load_state()
    if not state:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    if state.get("org_id") != user.organization_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return state


class StartPipelineRequest(BaseModel):
    project_id: str = ""
    client_id: str
    raw_brief: str
    output_language: str = "auto"  # "zh" | "en" | "auto"


class ConfirmRequest(BaseModel):
    node: str
    action: str             # "confirm" | "revise" | "rerun"
    feedback: str | None = None
    refresh_research: bool = False
    edits: dict | None = None
    rerun_from: str | None = None       # for action="rerun" from hitl_strategy
    flagged_indices: list[int] = []     # for hitl_gallery


class RerunRequest(BaseModel):
    rerun_from: str
    refresh_research: bool = False
    feedback: str | None = None


@router.post("/start", status_code=status.HTTP_202_ACCEPTED)
async def start_pipeline(
    request: StartPipelineRequest,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
):
    pipeline_id = str(uuid.uuid4())

    initial_state = {
        "client_id": request.client_id,
        "project_id": request.project_id,
        "proposal_id": pipeline_id,
        "org_id": user.organization_id,
        "raw_brief": request.raw_brief,
        "output_language": request.output_language,
    }

    executor = PipelineExecutor(pipeline_id)
    background_tasks.add_task(executor.start, initial_state)

    return {"pipeline_id": pipeline_id, "status": "started"}


@router.post("/{pipeline_id}/confirm", status_code=status.HTTP_202_ACCEPTED)
async def confirm_node(
    pipeline_id: str,
    request: ConfirmRequest,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
):
    """Submit a HITL response to resume the pipeline.

    Starts a short-lived background task that feeds the response via Command(resume=...)
    into the LangGraph checkpoint and runs until the next interrupt or completion.
    Returns 202 immediately — the pipeline continues asynchronously.
    """
    executor = PipelineExecutor(pipeline_id)
    await _require_owner(executor, user)
    current = await executor.get_status()

    if current.get("status") != "paused":
        raise HTTPException(status_code=400, detail="Pipeline is not paused at a HITL node")

    current_node = current.get("current_node")
    if not current_node or request.node != current_node:
        raise HTTPException(
            status_code=400,
            detail=f"Pipeline is paused at '{current_node}', not '{request.node}'",
        )

    # Optimistic lock: reject duplicate confirms while resume is in flight
    await executor.set_status("running", current_node)

    response = {
        "action": request.action,
        "feedback": request.feedback,
        "refresh_research": request.refresh_research,
        "edits": request.edits,
        "rerun_from": request.rerun_from,
        "flagged_indices": request.flagged_indices,
    }
    background_tasks.add_task(executor.resume_pipeline, response)

    return {"status": "accepted", "node": request.node}


@router.post("/{pipeline_id}/rerun", status_code=status.HTTP_202_ACCEPTED)
async def rerun_from_node(
    pipeline_id: str,
    request: RerunRequest,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
):
    executor = PipelineExecutor(pipeline_id)
    state = await _require_owner(executor, user)

    state["rerun_from"] = request.rerun_from
    state["rerun_refresh_research"] = request.refresh_research
    if request.feedback:
        state["strategy_feedback"] = request.feedback

    new_executor = PipelineExecutor(pipeline_id)
    background_tasks.add_task(new_executor.start, state, request.rerun_from)

    return {"status": "rerun_started", "from_node": request.rerun_from}


@router.post("/{pipeline_id}/recover", status_code=status.HTTP_200_OK)
async def recover_pipeline(
    pipeline_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Recover a pipeline stuck in 'running' after a process restart.

    Reads the LangGraph checkpoint:
    - If paused at a HITL interrupt → restores status to 'paused' (user can re-confirm)
    - Otherwise → marks status as 'error' (user should rerun)
    """
    executor = PipelineExecutor(pipeline_id)
    await _require_owner(executor, user)
    result = await executor.recover(stale_threshold=0)  # caller decides staleness
    return result


@router.get("/{pipeline_id}/status")
async def get_pipeline_status(
    pipeline_id: str, user: CurrentUser = Depends(get_current_user)
):
    executor = PipelineExecutor(pipeline_id)
    state = await _require_owner(executor, user)
    status_info = await executor.get_status()

    # Auto-recover pipelines that appear stuck in 'running' for > 5 minutes
    if status_info.get("status") == "running":
        if time.time() - status_info.get("updated_at", 0) > 300:
            await executor.recover(stale_threshold=300)
            status_info = await executor.get_status()

    return {
        "pipeline_id": pipeline_id,
        "status": status_info.get("status", "unknown"),
        "current_node": status_info.get("current_node"),
        "brief_confirmed": (state or {}).get("brief_confirmed", False),
        "strategy_confirmed": (state or {}).get("strategy_confirmed", False),
        "structure_confirmed": (state or {}).get("structure_confirmed", False),
        "slides_confirmed": (state or {}).get("slides_confirmed", False),
        "pptx_path": (state or {}).get("pptx_path"),
        "research_fetched_at": (state or {}).get("research_fetched_at"),
    }


@router.get("/{pipeline_id}/brief")
async def get_brief(
    pipeline_id: str, user: CurrentUser = Depends(get_current_user)
):
    executor = PipelineExecutor(pipeline_id)
    state = await _require_owner(executor, user)
    return {
        "structured_brief": state.get("structured_brief", {}),
        "raw_brief": state.get("raw_brief", ""),
    }


@router.get("/{pipeline_id}/strategy")
async def get_strategy(
    pipeline_id: str, user: CurrentUser = Depends(get_current_user)
):
    executor = PipelineExecutor(pipeline_id)
    state = await _require_owner(executor, user)
    return {
        "strategy_result": state.get("strategy_result", {}),
        "research_result": state.get("research_result", {}),
        "brand_check_passed": state.get("brand_check_passed"),
    }


@router.get("/{pipeline_id}/media-plan")
async def get_media_plan(
    pipeline_id: str, user: CurrentUser = Depends(get_current_user)
):
    executor = PipelineExecutor(pipeline_id)
    state = await _require_owner(executor, user)
    return {
        "media_plan": state.get("media_plan", {}),
    }


@router.get("/{pipeline_id}/slides")
async def get_slides(
    pipeline_id: str, user: CurrentUser = Depends(get_current_user)
):
    executor = PipelineExecutor(pipeline_id)
    state = await _require_owner(executor, user)
    return {
        "slides": state.get("slides", []),
        "narrative_suggestions": state.get("narrative_suggestions", []),
        "deck_structure": state.get("deck_structure", []),
    }
