from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.api.v1.permissions import CurrentUser, get_current_user
from backend.core.database.connection import get_database
from backend.core.database.repositories.feedback import FeedbackRepository
from backend.core.database.repositories.proposals import ProposalRepository
from backend.core.graph.executor import PipelineExecutor
from backend.core.models.feedback import RERUN_SUGGESTIONS, FeedbackTarget

router = APIRouter()


class FeedbackRequest(BaseModel):
    target: FeedbackTarget = FeedbackTarget.OVERALL
    content: str
    approved_directions: list[str] = []
    rejected_directions: list[str] = []
    tags: list[str] = []
    trigger_rerun: bool = False


class FeedbackResponse(BaseModel):
    status: str
    suggested_rerun_node: str | None = None
    rerun_triggered: bool = False


@router.get("")
async def list_proposals(
    project_id: str | None = None, user: CurrentUser = Depends(get_current_user)
):
    db = await get_database()
    repo = ProposalRepository(db)
    if project_id:
        return await repo.find_by_project(project_id)
    return []


@router.get("/{proposal_id}")
async def get_proposal(proposal_id: str, user: CurrentUser = Depends(get_current_user)):
    executor = PipelineExecutor(proposal_id)
    state = await executor.load_state()
    if state:
        return {
            "proposal_id": proposal_id,
            "structured_brief": state.get("structured_brief"),
            "strategy_result": state.get("strategy_result"),
            "deck_structure": state.get("deck_structure"),
            "slides": state.get("slides"),
            "pptx_path": state.get("pptx_path"),
        }

    db = await get_database()
    repo = ProposalRepository(db)
    doc = await repo.get_by_id(proposal_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return doc


@router.get("/{proposal_id}/download")
async def download_proposal(proposal_id: str, user: CurrentUser = Depends(get_current_user)):
    executor = PipelineExecutor(proposal_id)
    state = await executor.load_state()
    pptx_path = (state or {}).get("pptx_path")

    if not pptx_path:
        db = await get_database()
        repo = ProposalRepository(db)
        doc = await repo.get_by_id(proposal_id)
        pptx_path = (doc or {}).get("pptx_path")

    if not pptx_path or not Path(pptx_path).exists():
        raise HTTPException(status_code=404, detail="PPT file not found")

    return FileResponse(
        path=pptx_path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=f"proposal_{proposal_id}.pptx",
    )


@router.get("/{proposal_id}/feedback")
async def list_feedback(proposal_id: str, user: CurrentUser = Depends(get_current_user)):
    db = await get_database()
    repo = FeedbackRepository(db)
    return await repo.find({"proposal_id": proposal_id})


@router.post("/{proposal_id}/feedback", status_code=status.HTTP_201_CREATED, response_model=FeedbackResponse)
async def submit_feedback(
    proposal_id: str, request: FeedbackRequest, user: CurrentUser = Depends(get_current_user)
):
    executor = PipelineExecutor(proposal_id)
    state = await executor.load_state()
    client_id = (state or {}).get("client_id", "")
    project_id = (state or {}).get("project_id")

    suggested_node = RERUN_SUGGESTIONS.get(request.target)

    db = await get_database()
    repo = FeedbackRepository(db)

    feedback_id = await repo.create({
        "proposal_id": proposal_id,
        "client_id": client_id,
        "project_id": project_id,
        "target": request.target.value,
        "content": request.content,
        "approved_directions": request.approved_directions,
        "rejected_directions": request.rejected_directions,
        "tags": request.tags,
        "rerun_triggered": request.trigger_rerun,
        "rerun_from_node": suggested_node if request.trigger_rerun else None,
        "embedded": False,
        "created_at": datetime.utcnow(),
    })

    # Embed approved directions into brand namespace for future use
    if request.approved_directions:
        from backend.core.rag.feedback_embedder import embed_feedback_directions
        await embed_feedback_directions(client_id, feedback_id, request.approved_directions)

    # Trigger rerun if requested
    rerun_triggered = False
    if request.trigger_rerun and suggested_node and state:
        await executor.resume({"action": "rerun", "rerun_from": suggested_node})
        rerun_triggered = True

    return FeedbackResponse(
        status="feedback_recorded",
        suggested_rerun_node=suggested_node,
        rerun_triggered=rerun_triggered,
    )
