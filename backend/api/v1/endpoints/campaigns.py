"""Campaign Knowledge Base endpoints: review, confirm, and query campaign records."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from backend.api.v1.permissions import CurrentUser, get_current_user
from backend.core.database.connection import get_database
from backend.core.models.campaign_record import ConfirmationStatus

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
    user: CurrentUser = Depends(get_current_user),
):
    """Human confirms a campaign record, optionally applying edits."""
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

    return {"record_id": record_id, "status": "confirmed"}
