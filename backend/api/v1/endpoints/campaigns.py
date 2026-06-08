"""Campaign Knowledge Base endpoints: review, confirm, and query campaign records."""
import logging
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel

from backend.api.v1.permissions import CurrentUser, get_current_user
from backend.core.config import settings
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
    query: dict = {"org_id": user.organization_id}
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
    query: dict = {
        "org_id": user.organization_id,
        "status": ConfirmationStatus.PENDING.value,
    }
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
    mongo_query: dict = {
        "org_id": user.organization_id,
        "status": ConfirmationStatus.CONFIRMED.value,
    }

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


ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".ppt"}
MAX_FILE_SIZE = 30 * 1024 * 1024  # 30 MB
CHUNK_SIZE = 64 * 1024


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_recap(
    client_id: str = Form(...),
    file: UploadFile = File(...),
    project_id: str = Form(""),
    user: CurrentUser = Depends(get_current_user),
):
    """Upload a recap / case-study document directly to the Campaign KB.

    Triggers async extraction of campaign records for human review.
    Associates with a client; project association is optional.
    """
    from backend.core.rag.archive_process import process_archive_task

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Verify client exists
    db = await get_database()
    client_doc = await db["clients"].find_one({"_id": __import__("bson").ObjectId(client_id)})
    if not client_doc:
        raise HTTPException(status_code=404, detail="Client not found")

    archive_id = str(uuid.uuid4())
    storage_dir = Path(settings.file_storage_dir) / client_id
    storage_dir.mkdir(parents=True, exist_ok=True)
    dest = storage_dir / f"{archive_id}{ext}"

    total = 0
    with open(dest, "wb") as f:
        while chunk := await file.read(CHUNK_SIZE):
            total += len(chunk)
            if total > MAX_FILE_SIZE:
                dest.unlink(missing_ok=True)
                raise HTTPException(status_code=400, detail="File exceeds 30 MB limit")
            f.write(chunk)

    await db["project_archives"].insert_one({
        "_id": archive_id,
        "project_id": project_id,
        "client_id": client_id,
        "filename": file.filename,
        "storage_path": str(dest),
        "status": "pending",
        "uploaded_by": user.user_id,
        "uploaded_at": datetime.utcnow(),
        "source": "campaign_kb_direct",
    })

    process_archive_task.delay(
        archive_id=archive_id,
        storage_path=str(dest),
        filename=file.filename,
        client_id=client_id,
        project_id=project_id,
        org_id=user.organization_id,
    )

    return {"archive_id": archive_id, "status": "processing"}


@router.get("/{record_id}")
async def get_campaign_record(
    record_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Get a single campaign record for review."""
    db = await get_database()
    doc = await db["campaign_records"].find_one({
        "_id": record_id,
        "org_id": user.organization_id,
    })
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    doc["id"] = str(doc.pop("_id"))
    return doc


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign_record(
    record_id: str,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
):
    """Delete a campaign record and all associated data.

    Pending records: deletes MongoDB record only.
    Confirmed records: also purges propositions from MongoDB and Pinecone.
    """
    db = await get_database()
    doc = await db["campaign_records"].find_one({
        "_id": record_id,
        "org_id": user.organization_id,
    })
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")

    is_confirmed = doc.get("status") == ConfirmationStatus.CONFIRMED.value

    # Always delete the record itself
    await db["campaign_records"].delete_one({"_id": record_id})

    if is_confirmed:
        # Clean up propositions + Pinecone in background so response is fast
        background_tasks.add_task(
            _purge_confirmed_record, record_id, user.organization_id
        )


async def _purge_confirmed_record(record_id: str, org_id: str):
    """Remove propositions from MongoDB and Pinecone after a confirmed record is deleted."""
    from backend.core.rag.indexer import _get_index

    db = await get_database()

    # Get proposition indices before deleting so we can build Pinecone vector IDs
    prop_docs = await db["campaign_propositions"].find(
        {"campaign_record_id": record_id}
    ).to_list(length=200)
    prop_indices = [p["index"] for p in prop_docs]

    # Delete propositions from MongoDB
    await db["campaign_propositions"].delete_many({"campaign_record_id": record_id})

    # Delete vectors from Pinecone
    if prop_indices:
        vector_ids = [f"camp_{record_id}_{i}" for i in prop_indices]
        namespace = f"campaign_knowledge_{org_id}"
        try:
            index = _get_index()
            # Pinecone delete accepts up to 1000 IDs per call
            for start in range(0, len(vector_ids), 1000):
                index.delete(ids=vector_ids[start:start + 1000], namespace=namespace)
            logger.info(f"Purged {len(vector_ids)} Pinecone vectors for record {record_id}")
        except Exception as e:
            logger.error(f"Pinecone purge failed for record {record_id}: {e}")


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
    org_id = user.organization_id
    doc = await db["campaign_records"].find_one({
        "_id": record_id,
        "org_id": org_id,
    })
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")

    update: dict = {
        "status": ConfirmationStatus.CONFIRMED.value,
        "confirmed_by": user.user_id,
        "confirmed_at": datetime.utcnow(),
    }

    if body.edits:
        for module, fields in body.edits.items():
            if isinstance(fields, dict):
                for field, value in fields.items():
                    update[f"{module}.{field}"] = value
            else:
                update[module] = fields

    await db["campaign_records"].update_one({"_id": record_id}, {"$set": update})

    # Fetch updated record for proposition extraction
    confirmed_doc = await db["campaign_records"].find_one({"_id": record_id})

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
