from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.api.v1.permissions import CurrentUser, get_current_user
from backend.core.database.connection import get_database
from backend.core.database.repositories.projects import ProjectRepository

router = APIRouter()


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
