"""Campaign Knowledge Base endpoints: review, confirm, and query campaign records."""
import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel

from backend.api.v1.permissions import CurrentUser, get_current_user
from backend.core.database.connection import get_database
from backend.core.models.campaign_record import ConfirmationStatus
from backend.core.rag.campaign_index import index_campaign_propositions

logger = logging.getLogger(__name__)

router = APIRouter()


class ConfirmRequest(BaseModel):
    """Partial edits applied during human confirmation."""
    edits: dict = {}


@router.get("")
async def list_campaign_records(
    client_id: str | None = None,
    status_filter: ConfirmationStatus | None = None,
    user: CurrentUser = Depends(get_current_user),
):
    """List campaign records, optionally filtered by client or status."""
    db = await get_database()
    query: dict = {}
    if client_id:
        query["client_id"] = client_id
    if status_filter:
        query["status"] = status_filter.value

    cursor = db["campaign_records"].find(query).sort("created_at", -1)
    records = await cursor.to_list(length=50)
    for r in records:
        r["id"] = str(r.pop("_id"))
    return records


@router.get("/pending")
async def list_pending_records(
    client_id: str | None = None,
    user: CurrentUser = Depends(get_current_user),
):
    """List records awaiting human confirmation."""
    db = await get_database()
    query: dict = {"status": ConfirmationStatus.PENDING.value}
    if client_id:
        query["client_id"] = client_id

    cursor = db["campaign_records"].find(query).sort("created_at", -1)
    records = await cursor.to_list(length=50)
    for r in records:
        r["id"] = str(r.pop("_id"))
    return records


@router.get("/search")
async def search_campaign_records(
    query: str = Query(..., description="Free-text search query"),
    client_id: str | None = None,
    industry: str | None = None,
    campaign_type: str | None = None,
    user: CurrentUser = Depends(get_current_user),
):
    """Search confirmed campaign records by metadata filters.

    Note: Full semantic search via Pinecone comes in Phase 5.3.
    This endpoint provides basic metadata-based filtering for now.
    """
    db = await get_database()
    mongo_query: dict = {"status": ConfirmationStatus.CONFIRMED.value}

    if client_id:
        mongo_query["client_id"] = client_id
    if industry:
        mongo_query["meta.industry"] = {"$regex": industry, "$options": "i"}
    if campaign_type:
        mongo_query["meta.campaign_type"] = campaign_type

    cursor = db["campaign_records"].find(mongo_query).sort("created_at", -1)
    records = await cursor.to_list(length=20)
    for r in records:
        r["id"] = str(r.pop("_id"))
    return records


@router.get("/{record_id}")
async def get_campaign_record(
    record_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Get a single campaign record for review."""
    db = await get_database()
    doc = await db["campaign_records"].find_one({"_id": record_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    doc["id"] = str(doc.pop("_id"))
    return doc


@router.put("/{record_id}/confirm")
async def confirm_campaign_record(
    record_id: str,
    body: ConfirmRequest,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
):
    """Human confirms a campaign record, optionally applying edits.

    After confirmation, proposition extraction + vectorization runs in background.
    """
    db = await get_database()
    doc = await db["campaign_records"].find_one({"_id": record_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")

    update: dict = {
        "status": ConfirmationStatus.CONFIRMED.value,
        "confirmed_by": user.user_id,
        "confirmed_at": datetime.utcnow(),
    }

    if body.edits:
        update.update(body.edits)

    await db["campaign_records"].update_one({"_id": record_id}, {"$set": update})

    # Fetch updated record for proposition extraction
    confirmed_doc = await db["campaign_records"].find_one({"_id": record_id})
    org_id = user.organization_id

    background_tasks.add_task(
        _index_propositions_safe, record_id, confirmed_doc, org_id
    )

    return {"record_id": record_id, "status": "confirmed"}


async def _index_propositions_safe(record_id: str, record: dict, org_id: str):
    """Wrapper that catches errors so background task doesn't crash silently."""
    try:
        count = await index_campaign_propositions(record_id, record, org_id)
        logger.info(f"Proposition indexing complete: {count} propositions for {record_id}")
    except Exception as e:
        logger.error(f"Proposition indexing failed for {record_id}: {e}")
