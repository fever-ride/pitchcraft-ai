from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.api.v1.permissions import CurrentUser, get_current_user
from backend.core.database.connection import get_database
from backend.core.database.repositories.feedback import FeedbackRepository
from backend.core.database.repositories.proposals import ProposalRepository
from backend.core.database.repositories.proposal_versions import ProposalVersionRepository
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
    proposal_id: str,
    request: FeedbackRequest,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
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

    # Embed approved directions into Pinecone + mirror into BrandProfile
    if request.approved_directions:
        from backend.core.rag.feedback_embedder import embed_feedback_directions
        await embed_feedback_directions(client_id, feedback_id, request.approved_directions)

    # Mirror rejected directions into BrandProfile so phase1 + brand_check see them
    if request.rejected_directions and client_id:
        from backend.core.database.repositories.brand_profiles import BrandProfileRepository
        bp_repo = BrandProfileRepository(db)
        await bp_repo.add_feedback_directions(client_id, rejected=request.rejected_directions)

    # Trigger rerun if requested — start a fresh run from the suggested node.
    # executor.resume() only works while a pipeline is paused at a HITL interrupt;
    # after completion, we must call run() directly as a background task.
    rerun_triggered = False
    if request.trigger_rerun and suggested_node and state:
        rerun_executor = PipelineExecutor(proposal_id)
        background_tasks.add_task(rerun_executor.start, state, suggested_node)
        rerun_triggered = True

    return FeedbackResponse(
        status="feedback_recorded",
        suggested_rerun_node=suggested_node,
        rerun_triggered=rerun_triggered,
    )


# --- Version Management ---


class VersionNoteRequest(BaseModel):
    note: str = ""


@router.get("/{proposal_id}/versions")
async def list_versions(proposal_id: str, user: CurrentUser = Depends(get_current_user)):
    db = await get_database()
    repo = ProposalVersionRepository(db)
    versions = await repo.find_by_proposal(proposal_id)
    return [
        {
            "_id": v["_id"],
            "version": v["version"],
            "trigger": v.get("trigger", ""),
            "note": v.get("note", ""),
            "created_at": v.get("created_at"),
        }
        for v in versions
    ]


@router.get("/{proposal_id}/versions/{version}")
async def get_version(
    proposal_id: str, version: int, user: CurrentUser = Depends(get_current_user)
):
    db = await get_database()
    repo = ProposalVersionRepository(db)
    doc = await repo.get_version(proposal_id, version)
    if not doc:
        raise HTTPException(status_code=404, detail="Version not found")
    return doc


@router.put("/{proposal_id}/versions/{version}/note")
async def update_version_note(
    proposal_id: str,
    version: int,
    request: VersionNoteRequest,
    user: CurrentUser = Depends(get_current_user),
):
    db = await get_database()
    repo = ProposalVersionRepository(db)
    doc = await repo.get_version(proposal_id, version)
    if not doc:
        raise HTTPException(status_code=404, detail="Version not found")
    await repo.update(doc["_id"], {"note": request.note})
    return {"status": "updated"}


@router.get("/{proposal_id}/versions/{v1}/diff/{v2}")
async def diff_versions(
    proposal_id: str, v1: int, v2: int, user: CurrentUser = Depends(get_current_user)
):
    db = await get_database()
    repo = ProposalVersionRepository(db)
    doc1 = await repo.get_version(proposal_id, v1)
    doc2 = await repo.get_version(proposal_id, v2)
    if not doc1 or not doc2:
        raise HTTPException(status_code=404, detail="Version not found")

    snap1 = doc1.get("snapshot", {})
    snap2 = doc2.get("snapshot", {})

    diff = {}
    all_keys = set(list(snap1.keys()) + list(snap2.keys()))
    for key in all_keys:
        val1 = snap1.get(key)
        val2 = snap2.get(key)
        if val1 != val2:
            diff[key] = {"v1": val1, "v2": val2}

    return {
        "proposal_id": proposal_id,
        "v1": v1,
        "v2": v2,
        "changed_fields": list(diff.keys()),
        "diff": diff,
    }


@router.post("/{proposal_id}/versions/{version}/rollback")
async def rollback_to_version(
    proposal_id: str, version: int, user: CurrentUser = Depends(get_current_user)
):
    db = await get_database()
    repo = ProposalVersionRepository(db)
    target = await repo.get_version(proposal_id, version)
    if not target:
        raise HTTPException(status_code=404, detail="Version not found")

    snapshot = target.get("snapshot", {})

    # Create a new version from the old snapshot (rollback is non-destructive)
    state_for_save = {
        **snapshot,
        "proposal_id": proposal_id,
        "project_id": target.get("project_id", ""),
        "client_id": target.get("client_id", ""),
    }
    new_version = await repo.save_version(
        proposal_id,
        state_for_save,
        trigger=f"rollback_from_v{version}",
        note=f"Rolled back to version {version}",
    )

    # Update Redis state so the active proposal reflects the rollback
    executor = PipelineExecutor(proposal_id)
    current_state = await executor.load_state()
    if current_state:
        current_state.update(snapshot)
        await executor.save_state(current_state)

    return {"status": "rolled_back", "new_version": new_version}
