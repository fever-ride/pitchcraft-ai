from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.api.v1.permissions import CurrentUser, get_current_user
from backend.core.database.connection import get_database
from backend.core.database.repositories.feedback import FeedbackRepository
from backend.core.database.repositories.proposals import ProposalRepository
from backend.core.graph.executor import PipelineExecutor

router = APIRouter()


class FeedbackRequest(BaseModel):
    content: str
    approved_directions: list[str] = []
    rejected_directions: list[str] = []
    rerun_from_node: str | None = None


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


@router.post("/{proposal_id}/feedback", status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    proposal_id: str, request: FeedbackRequest, user: CurrentUser = Depends(get_current_user)
):
    executor = PipelineExecutor(proposal_id)
    state = await executor.load_state()
    client_id = (state or {}).get("client_id", "")

    db = await get_database()
    repo = FeedbackRepository(db)
    from datetime import datetime

    await repo.create({
        "proposal_id": proposal_id,
        "client_id": client_id,
        "content": request.content,
        "approved_directions": request.approved_directions,
        "rejected_directions": request.rejected_directions,
        "rerun_triggered": request.rerun_from_node is not None,
        "rerun_from_node": request.rerun_from_node,
        "created_at": datetime.utcnow(),
    })

    return {"status": "feedback_recorded"}
