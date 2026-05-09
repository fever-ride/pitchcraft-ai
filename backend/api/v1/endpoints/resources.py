from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from backend.api.v1.permissions import CurrentUser, get_current_user
from backend.core.database.connection import get_database
from backend.core.models.resource import FRESHNESS_THRESHOLD_DAYS, ResourceStatus, normalize_platform, parse_follower_count, resource_namespace
from backend.core.rag.embedder import embed_texts
from backend.core.rag.indexer import upsert_vectors
from backend.core.rag.resource_import import import_resources as do_import, refresh_resource_embedding

router = APIRouter()


class CreateResourceRequest(BaseModel):
    type: str  # kol / media / vendor / placement
    name: str
    platform: str = ""
    tags: list[str] = []
    categories: list[str] = []
    content_style: str | None = None
    audience_tags: list[str] = []
    past_cpe: str | None = None
    followers: str | None = None
    pricing: dict | None = None
    metadata: dict = {}


def _resource_to_embed_text(r: dict) -> str:
    """Build embedding text for a single resource (same logic as resource_import)."""
    parts = [f"Name: {r.get('name', '')}", f"Type: {r.get('type', '')}"]
    if r.get("platform"):
        parts.append(f"Platform: {r['platform']}")
    if r.get("followers"):
        parts.append(f"Followers: {r['followers']}")
    if r.get("categories"):
        cats = r["categories"]
        parts.append(f"Categories: {', '.join(cats) if isinstance(cats, list) else cats}")
    if r.get("content_style"):
        parts.append(f"Content Style: {r['content_style']}")
    if r.get("audience_tags"):
        tags = r["audience_tags"]
        parts.append(f"Audience: {', '.join(tags) if isinstance(tags, list) else tags}")
    if r.get("past_cpe"):
        parts.append(f"Past CPE: {r['past_cpe']}")
    if r.get("tags"):
        tags = r["tags"]
        parts.append(f"Tags: {', '.join(tags) if isinstance(tags, list) else tags}")
    if r.get("pricing"):
        parts.append(f"Pricing: {r['pricing']}")
    return " | ".join(parts)


def _enrich_with_freshness(doc: dict) -> dict:
    """Add freshness info and pricing disclaimer to resource response."""
    doc["_id"] = str(doc["_id"])
    doc["pricing_note"] = "reference price — confirm with resource before committing"

    verified_at = doc.get("last_verified_at")
    if not verified_at:
        doc["freshness"] = "never verified"
        doc["is_stale"] = True
    else:
        if isinstance(verified_at, str):
            verified_at = datetime.fromisoformat(verified_at)
        age_days = (datetime.utcnow() - verified_at).days
        if age_days <= 30:
            doc["freshness"] = "recent"
            doc["is_stale"] = False
        elif age_days <= FRESHNESS_THRESHOLD_DAYS:
            doc["freshness"] = f"verified {age_days} days ago"
            doc["is_stale"] = False
        else:
            months = age_days // 30
            doc["freshness"] = f"data may be outdated ({months} months since last verification)"
            doc["is_stale"] = True

    return doc


@router.get("")
async def list_resources(
    client_id: str,
    type: str | None = None,
    status_filter: str | None = None,
    min_followers: int | None = None,
    user: CurrentUser = Depends(get_current_user),
):
    db = await get_database()
    query: dict = {"client_id": client_id}
    if type:
        query["type"] = type
    if status_filter:
        query["status"] = status_filter
    else:
        query["status"] = {"$ne": ResourceStatus.INACTIVE.value}
    if min_followers is not None:
        query["followers_count"] = {"$gte": min_followers}

    cursor = db["resources"].find(query).limit(200)
    results = []
    async for doc in cursor:
        results.append(_enrich_with_freshness(doc))
    return results


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_resource(
    request: CreateResourceRequest,
    client_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    db = await get_database()
    doc = request.model_dump()
    doc["client_id"] = client_id
    doc["status"] = ResourceStatus.ACTIVE.value
    doc["last_verified_at"] = datetime.utcnow()
    doc["followers_count"] = parse_follower_count(request.followers)
    result = await db["resources"].insert_one(doc)

    resource_id = str(result.inserted_id)
    text = _resource_to_embed_text(doc)
    embeddings = await embed_texts([text])
    ns = resource_namespace(doc.get("type", "kol"), client_id)
    extra_meta = {
        "name": doc.get("name", ""),
        "type": doc.get("type", "kol"),
        "platform": normalize_platform(doc.get("platform", "")),
        "status": doc.get("status", "active"),
        "followers_count": doc.get("followers_count") or 0,
        "tags": ", ".join(doc.get("tags", [])),
    }
    upsert_vectors(ns, resource_id, [text], embeddings, extra_metadata=[extra_meta])

    return {"status": "created", "id": resource_id}


@router.patch("/{resource_id}/verify")
async def verify_resource(
    resource_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Mark a resource as freshly verified."""
    db = await get_database()
    from bson import ObjectId
    result = await db["resources"].update_one(
        {"_id": ObjectId(resource_id)},
        {"$set": {"last_verified_at": datetime.utcnow()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Resource not found")
    return {"status": "verified"}


@router.patch("/{resource_id}/status")
async def update_resource_status(
    resource_id: str,
    new_status: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Update resource availability status (active/inactive)."""
    if new_status not in (s.value for s in ResourceStatus):
        raise HTTPException(status_code=400, detail="Invalid status. Must be: active, inactive")
    db = await get_database()
    from bson import ObjectId
    result = await db["resources"].update_one(
        {"_id": ObjectId(resource_id)},
        {"$set": {"status": new_status}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Resource not found")
    return {"status": "updated", "new_status": new_status}


class UpdateResourceRequest(BaseModel):
    name: str | None = None
    platform: str | None = None
    tags: list[str] | None = None
    categories: list[str] | None = None
    content_style: str | None = None
    audience_tags: list[str] | None = None
    past_cpe: str | None = None
    followers: str | None = None
    pricing: dict | None = None
    metadata: dict | None = None
    notes: str | None = None


@router.patch("/{resource_id}")
async def update_resource(
    resource_id: str,
    request: UpdateResourceRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Update resource fields and refresh Pinecone embedding."""
    from bson import ObjectId
    db = await get_database()
    collection = db["resources"]

    doc = await collection.find_one({"_id": ObjectId(resource_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Resource not found")

    updates = {k: v for k, v in request.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    if "followers" in updates:
        updates["followers_count"] = parse_follower_count(updates["followers"])

    await collection.update_one({"_id": ObjectId(resource_id)}, {"$set": updates})

    updated_doc = await collection.find_one({"_id": ObjectId(resource_id)})
    client_id = updated_doc["client_id"]
    await refresh_resource_embedding(updated_doc, client_id)

    return {"status": "updated", "id": resource_id}


@router.post("/import", status_code=status.HTTP_202_ACCEPTED)
async def import_resources(
    file: UploadFile = File(...),
    client_id: str = Form(...),
    user: CurrentUser = Depends(get_current_user),
):
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only .xlsx files are supported")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Excel file exceeds 10 MB limit")
    result = await do_import(content, client_id)
    return result
