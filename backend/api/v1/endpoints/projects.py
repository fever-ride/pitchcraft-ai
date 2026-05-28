import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from backend.api.v1.permissions import CurrentUser, get_current_user
from backend.core.config import settings
from backend.core.database.connection import get_database
from backend.core.database.repositories.projects import ProjectRepository

router = APIRouter()

ALLOWED_ARCHIVE_EXTENSIONS = {".pdf", ".docx", ".pptx", ".ppt"}
MAX_ARCHIVE_SIZE = 30 * 1024 * 1024  # 30 MB
CHUNK_SIZE = 64 * 1024


class CreateProjectRequest(BaseModel):
    client_id: str
    name: str


class UpdateProjectRequest(BaseModel):
    name: str | None = None
    status: str | None = None
    custom_deck_structure: list[dict] | None = None
    assigned_accounts: list[str] | None = None


@router.get("")
async def list_projects(client_id: str | None = None, user: CurrentUser = Depends(get_current_user)):
    db = await get_database()
    repo = ProjectRepository(db)
    if client_id:
        return await repo.find_accessible(client_id, user.user_id)
    return []


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project(request: CreateProjectRequest, user: CurrentUser = Depends(get_current_user)):
    db = await get_database()
    repo = ProjectRepository(db)
    project_id = await repo.create({
        "client_id": request.client_id,
        "name": request.name,
        "assigned_accounts": [user.user_id],
        "status": "draft",
        "custom_deck_structure": None,
        "created_at": datetime.utcnow(),
    })
    return {"project_id": project_id, "status": "created"}


@router.get("/{project_id}")
async def get_project(project_id: str, user: CurrentUser = Depends(get_current_user)):
    db = await get_database()
    repo = ProjectRepository(db)
    doc = await repo.get_by_id(project_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Project not found")
    return doc


@router.patch("/{project_id}")
async def update_project(
    project_id: str,
    request: UpdateProjectRequest,
    user: CurrentUser = Depends(get_current_user),
):
    db = await get_database()
    repo = ProjectRepository(db)
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    await repo.update(project_id, updates)
    return {"status": "updated"}


@router.post("/{project_id}/archive", status_code=status.HTTP_202_ACCEPTED)
async def archive_project(
    project_id: str,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
):
    """Upload a recap/case study report for structured knowledge extraction.

    Extracts: resource performance, CampaignRecord (pending human confirmation).
    Distributes to: resource collaboration_history, campaign_records collection.
    """
    from backend.core.rag.archive_process import process_archive_task

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_ARCHIVE_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Allowed: {', '.join(ALLOWED_ARCHIVE_EXTENSIONS)}")

    db = await get_database()
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    client_id = project["client_id"]
    archive_id = str(uuid.uuid4())
    storage_dir = Path(settings.file_storage_dir) / client_id
    storage_dir.mkdir(parents=True, exist_ok=True)
    dest = storage_dir / f"{archive_id}{ext}"

    total = 0
    with open(dest, "wb") as f:
        while chunk := await file.read(CHUNK_SIZE):
            total += len(chunk)
            if total > MAX_ARCHIVE_SIZE:
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


@router.get("/{project_id}/archive")
async def get_archive_status(
    project_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Get archive extraction status and results for a project."""
    db = await get_database()
    cursor = db["project_archives"].find({"project_id": project_id})
    results = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        results.append(doc)
    return results
