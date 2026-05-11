import asyncio
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel

from backend.api.v1.permissions import CurrentUser, get_current_user
from backend.core.graph.executor import PipelineExecutor
from backend.core.graph.state import RequestBudget

router = APIRouter()


class StartPipelineRequest(BaseModel):
    project_id: str
    client_id: str
    raw_brief: str
    output_language: str = "auto"  # "zh" | "en" | "auto"


class ConfirmRequest(BaseModel):
    node: str
    action: str  # "confirm" or "revise"
    feedback: str | None = None
    refresh_research: bool = False
    edits: dict | None = None


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
    background_tasks.add_task(executor.run, initial_state)

    return {"pipeline_id": pipeline_id, "status": "started"}


@router.post("/{pipeline_id}/confirm")
async def confirm_node(
    pipeline_id: str,
    request: ConfirmRequest,
    user: CurrentUser = Depends(get_current_user),
):
    executor = PipelineExecutor(pipeline_id)
    current = await executor.get_status()

    if current.get("status") != "paused":
        raise HTTPException(status_code=400, detail="Pipeline is not paused at a HITL node")

    await executor.resume({
        "action": request.action,
        "feedback": request.feedback,
        "refresh_research": request.refresh_research,
        "edits": request.edits,
    })

    return {"status": "resumed", "node": request.node}


@router.post("/{pipeline_id}/rerun")
async def rerun_from_node(
    pipeline_id: str,
    request: RerunRequest,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
):
    executor = PipelineExecutor(pipeline_id)
    state = await executor.load_state()

    if not state:
        raise HTTPException(status_code=404, detail="Pipeline state not found")

    state["rerun_from"] = request.rerun_from
    state["rerun_refresh_research"] = request.refresh_research
    if request.feedback:
        state["strategy_feedback"] = request.feedback

    new_executor = PipelineExecutor(pipeline_id)
    background_tasks.add_task(new_executor.run, state, request.rerun_from)

    return {"status": "rerun_started", "from_node": request.rerun_from}


@router.get("/{pipeline_id}/status")
async def get_pipeline_status(
    pipeline_id: str, user: CurrentUser = Depends(get_current_user)
):
    executor = PipelineExecutor(pipeline_id)
    status_info = await executor.get_status()
    state = await executor.load_state()

    if not state and status_info.get("status") == "unknown":
        raise HTTPException(status_code=404, detail="Pipeline not found")

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
    state = await executor.load_state()
    if not state:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return {
        "structured_brief": state.get("structured_brief", {}),
        "raw_brief": state.get("raw_brief", ""),
    }


@router.get("/{pipeline_id}/strategy")
async def get_strategy(
    pipeline_id: str, user: CurrentUser = Depends(get_current_user)
):
    executor = PipelineExecutor(pipeline_id)
    state = await executor.load_state()
    if not state:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return {
        "strategy_result": state.get("strategy_result", {}),
        "research_result": state.get("research_result", {}),
        "brand_check_passed": state.get("brand_check_passed"),
    }


@router.get("/{pipeline_id}/slides")
async def get_slides(
    pipeline_id: str, user: CurrentUser = Depends(get_current_user)
):
    executor = PipelineExecutor(pipeline_id)
    state = await executor.load_state()
    if not state:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return {
        "slides": state.get("slides", []),
        "narrative_suggestions": state.get("narrative_suggestions", []),
        "deck_structure": state.get("deck_structure", []),
    }
