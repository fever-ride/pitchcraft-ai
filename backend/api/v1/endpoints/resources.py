from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from backend.api.v1.permissions import CurrentUser, get_current_user
from backend.core.database.connection import get_database
from backend.core.rag.resource_import import import_resources as do_import

router = APIRouter()


class CreateResourceRequest(BaseModel):
    type: str  # kol / media / vendor / placement
    name: str
    tags: list[str] = []
    pricing: dict | None = None
    metadata: dict = {}


@router.get("")
async def list_resources(
    client_id: str,
    type: str | None = None,
    user: CurrentUser = Depends(get_current_user),
):
    db = await get_database()
    query: dict = {"client_id": client_id}
    if type:
        query["type"] = type
    cursor = db["resources"].find(query).limit(200)
    results = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        results.append(doc)
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
    result = await db["resources"].insert_one(doc)
    return {"status": "created", "id": str(result.inserted_id)}


@router.post("/import", status_code=status.HTTP_202_ACCEPTED)
async def import_resources(
    file: UploadFile = File(...),
    client_id: str = Form(...),
    user: CurrentUser = Depends(get_current_user),
):
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only .xlsx files are supported")

    content = await file.read()
    result = await do_import(content, client_id)
    return result
