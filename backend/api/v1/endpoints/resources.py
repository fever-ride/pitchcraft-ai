import json
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from backend.api.v1.permissions import CurrentUser, get_current_user
from backend.core.config import settings
from backend.core.database.connection import get_database
from backend.core.database.repositories.resources import ResourceRepository
from backend.core.models.resource import (
    FRESHNESS_THRESHOLD_DAYS,
    AudienceDemographics,
    ContentStyle,
    ResourceStatus,
    normalize_platform,
    parse_follower_count,
)
from backend.core.rag.resource_import import (
    import_resources_task,
    preview_import as do_preview,
    refresh_resource_embedding,
    repair_resource_embeddings,
)

router = APIRouter()


class CreateResourceRequest(BaseModel):
    type: str  # kol / media / vendor / placement
    name: str
    platforms: list[dict] = []    # list of {name, followers_raw?, followers_count?, profile_url?}
    # Convenience fields for single-platform creation — converted to platforms list
    platform: str = ""
    followers: str | None = None
    profile_url: str | None = None
    tier: str | None = None  # top / mid / tail / koc
    tags: list[str] = []
    categories: list[str] = []
    # Content style: use content_style_v2 (structured) when possible; content_style (str) as fallback
    content_style: str | None = None
    content_style_v2: ContentStyle | None = None
    # Audience: use audience_demographics (structured) when possible; audience_tags (flat) as fallback
    audience_tags: list[str] = []
    audience_demographics: AudienceDemographics | None = None
    past_cpe: str | None = None
    pricing: dict | None = None
    # Type-specific
    outlet_type: str | None = None        # media: newspaper / magazine / online / TV
    beat: str | None = None               # media: tech / lifestyle / finance …
    service_type: str | None = None       # vendor: event / photography / production
    region: str | None = None             # vendor / placement
    placement_type: str | None = None     # placement: OOH / elevator / cinema
    location: str | None = None           # placement
    audience_reach: str | None = None     # placement
    metadata: dict = {}


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
    scope: str = "shared",         # "shared" | "client" | "" (both)
    client_id: str = "",
    type: str | None = None,
    status_filter: str | None = None,
    min_followers: int | None = None,
    user: CurrentUser = Depends(get_current_user),
):
    """List resources.

    scope="shared"  → agency-wide pool (no client_id needed)
    scope="client"  → client-specific pool (client_id required)
    scope=""        → both pools merged
    """
    if scope == "client" and not client_id:
        raise HTTPException(status_code=400, detail="client_id is required when scope=client")

    org_id = user.organization_id
    db = await get_database()
    repo = ResourceRepository(db)
    docs = await repo.find_filtered(
        client_id=client_id,
        org_id=org_id,
        scope=scope,
        type=type,
        status_filter=status_filter,
        min_followers=min_followers,
    )
    return [_enrich_with_freshness(doc) for doc in docs]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_resource(
    request: CreateResourceRequest,
    background_tasks: BackgroundTasks,
    scope: str = "shared",
    client_id: str = "",
    user: CurrentUser = Depends(get_current_user),
):
    if scope == "client" and not client_id:
        raise HTTPException(status_code=400, detail="client_id is required when scope=client")

    org_id = user.organization_id
    db = await get_database()
    repo = ResourceRepository(db)
    doc = request.model_dump()
    doc["org_id"] = org_id
    doc["client_id"] = client_id
    doc["scope"] = scope
    doc["status"] = ResourceStatus.ACTIVE.value
    doc["last_verified_at"] = datetime.utcnow()
    # Convert flat platform/followers/profile_url to platforms list if platforms not provided
    if not doc.get("platforms") and (doc.get("platform") or doc.get("followers")):
        from backend.core.rag.resource_import import _build_platforms
        doc["platforms"] = _build_platforms(
            doc.pop("platform", ""),
            doc.pop("followers", "") or "",
            doc.pop("profile_url", "") or "",
        )
        doc["primary_platform"] = normalize_platform(doc["platforms"][0]["name"]) if doc["platforms"] else ""
        doc["total_followers_count"] = sum(p.get("followers_count") or 0 for p in doc["platforms"]) or None
    else:
        doc.pop("platform", None)
        doc.pop("followers", None)
        doc.pop("profile_url", None)
    resource_id = await repo.create(doc)
    doc["_id"] = resource_id  # needed by refresh_resource_embedding
    background_tasks.add_task(refresh_resource_embedding, doc)
    return {"status": "created", "id": resource_id}


@router.patch("/{resource_id}/verify")
async def verify_resource(
    resource_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Mark a resource as freshly verified."""
    db = await get_database()
    repo = ResourceRepository(db)
    if not await repo.get_by_id(resource_id):
        raise HTTPException(status_code=404, detail="Resource not found")
    await repo.verify(resource_id)
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
    repo = ResourceRepository(db)
    if not await repo.get_by_id(resource_id):
        raise HTTPException(status_code=404, detail="Resource not found")
    await repo.update_status(resource_id, new_status)
    return {"status": "updated", "new_status": new_status}


class UpdateResourceRequest(BaseModel):
    name: str | None = None
    platforms: list[dict] | None = None
    # Convenience fields — if provided alongside empty/absent platforms, they are converted
    platform: str | None = None
    followers: str | None = None
    tags: list[str] | None = None
    categories: list[str] | None = None
    content_style: str | None = None
    audience_tags: list[str] | None = None
    past_cpe: str | None = None
    pricing: dict | None = None
    metadata: dict | None = None
    notes: str | None = None


@router.patch("/{resource_id}")
async def update_resource(
    resource_id: str,
    request: UpdateResourceRequest,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
):
    """Update resource fields and refresh Pinecone embedding in the background."""
    db = await get_database()
    repo = ResourceRepository(db)

    doc = await repo.get_by_id(resource_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Resource not found")

    updates = {k: v for k, v in request.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Convert flat platform/followers to platforms list if platforms not explicitly set
    if not updates.get("platforms") and ("platform" in updates or "followers" in updates):
        from backend.core.rag.resource_import import _build_platforms
        raw_platform = updates.pop("platform", "")
        raw_followers = updates.pop("followers", "")
        platforms = _build_platforms(raw_platform, raw_followers, "")
        if platforms:
            updates["platforms"] = platforms
            updates["primary_platform"] = normalize_platform(platforms[0]["name"])
            updates["total_followers_count"] = sum(p.get("followers_count") or 0 for p in platforms) or None
    else:
        updates.pop("platform", None)
        updates.pop("followers", None)

    await repo.update(resource_id, updates)

    updated_doc = await repo.get_by_id(resource_id)
    background_tasks.add_task(refresh_resource_embedding, updated_doc)

    return {"status": "updated", "id": resource_id}


@router.post("/import/preview")
async def preview_import(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
):
    """Analyse Excel column headers without writing to DB.

    Returns three lists:
    - recognized: columns matched by static alias table
    - inferred:   columns matched by LLM (needs user confirmation)
    - ignored:    columns with no mapping found

    Use the returned mapping to build the column_mapping payload for /import/confirm.
    """
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only .xlsx files are supported")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Excel file exceeds 10 MB limit")
    return await do_preview(content)


@router.post("/import/confirm", status_code=status.HTTP_202_ACCEPTED)
async def confirm_import(
    file: UploadFile = File(...),
    scope: str = Form(default="shared"),
    client_id: str = Form(default=""),
    column_mapping: str = Form(default="{}"),
    user: CurrentUser = Depends(get_current_user),
):
    """Trigger import with a user-confirmed column mapping (from /import/preview).

    scope: "shared" (agency pool, default) or "client" (requires client_id)
    column_mapping: JSON object mapping raw header names to schema field names.
                    Use "ignore" as the value to explicitly skip a column.
    Example: {"达人账号": "ignore", "联系方式": "notes", "转发率": "past_cpe"}
    """
    if scope == "client" and not client_id:
        raise HTTPException(status_code=400, detail="client_id is required when scope=client")
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only .xlsx files are supported")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Excel file exceeds 10 MB limit")

    try:
        override_mapping: dict = json.loads(column_mapping) if column_mapping else {}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="column_mapping must be valid JSON")

    org_id = user.organization_id
    pool_id = org_id if scope == "shared" else client_id
    storage_dir = Path(settings.file_storage_dir) / "resource_imports" / pool_id
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / f"{uuid.uuid4().hex}.xlsx"
    storage_path.write_bytes(content)

    task = import_resources_task.delay(
        str(storage_path), client_id, override_mapping or None, org_id, scope
    )
    return {"task_id": task.id, "status": "queued"}


@router.post("/import", status_code=status.HTTP_202_ACCEPTED)
async def import_resources(
    file: UploadFile = File(...),
    scope: str = Form(default="shared"),
    client_id: str = Form(default=""),
    user: CurrentUser = Depends(get_current_user),
):
    """Kick off a background Celery task for bulk Excel import. Returns task_id for polling.

    scope="shared" → imports into the agency-wide pool (no client_id needed)
    scope="client" → imports into a client-specific pool (client_id required)
    """
    if scope == "client" and not client_id:
        raise HTTPException(status_code=400, detail="client_id is required when scope=client")
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only .xlsx files are supported")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Excel file exceeds 10 MB limit")

    org_id = user.organization_id
    # Save to shared storage volume (accessible by both API and Celery worker containers)
    pool_id = org_id if scope == "shared" else client_id
    storage_dir = Path(settings.file_storage_dir) / "resource_imports" / pool_id
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / f"{uuid.uuid4().hex}.xlsx"
    storage_path.write_bytes(content)

    task = import_resources_task.delay(str(storage_path), client_id, None, org_id, scope)
    return {"task_id": task.id, "status": "queued"}


@router.get("/import/{task_id}")
async def get_import_status(
    task_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Poll import task status. States: queued → processing → done / failed."""
    from backend.core.tasks import celery_app
    result = celery_app.AsyncResult(task_id)

    if result.state == "PENDING":
        return {"task_id": task_id, "status": "queued"}
    if result.state == "STARTED":
        return {"task_id": task_id, "status": "processing"}
    if result.state == "SUCCESS":
        return {"task_id": task_id, "status": "done", "result": result.get()}
    if result.state == "FAILURE":
        return {"task_id": task_id, "status": "failed", "error": str(result.result)}
    return {"task_id": task_id, "status": result.state.lower()}


@router.post("/repair-embeddings", status_code=status.HTTP_202_ACCEPTED)
async def repair_embeddings(
    background_tasks: BackgroundTasks,
    scope: str = "shared",
    client_id: str = "",
    user: CurrentUser = Depends(get_current_user),
):
    """Rebuild Pinecone vectors for all resources of a given pool.

    Use after a failed import where MongoDB records exist but Pinecone vectors are missing.
    Runs in the background — returns immediately.
    """
    if scope == "client" and not client_id:
        raise HTTPException(status_code=400, detail="client_id is required when scope=client")
    org_id = user.organization_id
    background_tasks.add_task(
        repair_resource_embeddings,
        client_id=client_id,
        org_id=org_id,
        scope=scope,
    )
    return {"status": "started", "message": f"Rebuilding embeddings for scope={scope} in background"}
