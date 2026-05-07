from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.api.v1.permissions import CurrentUser, Role, get_current_user
from backend.core.database.connection import get_database
from backend.core.database.repositories.clients import ClientRepository

router = APIRouter()


class CreateClientRequest(BaseModel):
    name: str
    industry: str | None = None


class DeckStructureUpdate(BaseModel):
    structure: list[dict]


@router.get("")
async def list_clients(user: CurrentUser = Depends(get_current_user)):
    db = await get_database()
    repo = ClientRepository(db)
    return await repo.find_by_organization(user.organization_id)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_client(request: CreateClientRequest, user: CurrentUser = Depends(get_current_user)):
    db = await get_database()
    repo = ClientRepository(db)
    client_id = await repo.create({
        "organization_id": user.organization_id,
        "lead_account_id": user.user_id,
        "name": request.name,
        "industry": request.industry,
        "default_deck_structure": None,
        "created_at": datetime.utcnow(),
    })
    return {"client_id": client_id, "status": "created"}


@router.get("/{client_id}")
async def get_client(client_id: str, user: CurrentUser = Depends(get_current_user)):
    db = await get_database()
    repo = ClientRepository(db)
    doc = await repo.get_by_id(client_id)
    if not doc or doc.get("organization_id") != user.organization_id:
        raise HTTPException(status_code=404, detail="Client not found")
    return doc


@router.patch("/{client_id}/deck-structure")
async def update_deck_structure(
    client_id: str,
    request: DeckStructureUpdate,
    user: CurrentUser = Depends(get_current_user),
):
    if user.role not in (Role.LEAD_ACCOUNT, Role.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires lead_account+")
    db = await get_database()
    repo = ClientRepository(db)
    await repo.update(client_id, {"default_deck_structure": request.structure})
    return {"status": "updated"}
