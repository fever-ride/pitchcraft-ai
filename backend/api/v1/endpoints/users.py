from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from backend.api.v1.permissions import CurrentUser, Role, get_current_user, require_role

router = APIRouter()


class InviteRequest(BaseModel):
    email: EmailStr
    name: str
    role: Role = Role.ACCOUNT


class RoleUpdateRequest(BaseModel):
    role: Role


@router.get("")
async def list_users(user: CurrentUser = Depends(get_current_user)):
    # TODO: return all users in user.organization_id
    return []


@router.post("/invite", status_code=status.HTTP_201_CREATED)
async def invite_user(request: InviteRequest, user: CurrentUser = Depends(get_current_user)):
    if user.role != Role.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    # TODO: create user, send invite email
    return {"status": "invited"}


@router.patch("/{user_id}/role")
async def update_role(
    user_id: str, request: RoleUpdateRequest, user: CurrentUser = Depends(get_current_user)
):
    if user.role != Role.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    # TODO: update user role in DB
    return {"status": "updated"}
