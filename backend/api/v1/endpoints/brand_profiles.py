"""Brand Profile endpoints: structured brand knowledge per client."""
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from backend.api.v1.permissions import CurrentUser, get_current_user
from backend.core.agents.brand_extract import extract_brand_profile
from backend.core.database.connection import get_database
from backend.core.database.repositories.brand_profiles import BrandProfileRepository
from backend.core.database.repositories.clients import ClientRepository
from backend.core.language.detector import detect_language
from backend.core.rag.parser import parse_file

logger = logging.getLogger(__name__)

router = APIRouter()


class BrandProfileUpsertRequest(BaseModel):
    org_id: str | None = None
    brand_name: str | None = None
    positioning: str | None = None
    personality: list[str] = []
    target_audience: str | None = None
    usage_scenes: list[str] = []
    user_pain_points: list[str] = []
    rtb: list[str] = []
    tone_principles: list[str] = []
    forbidden_directions: list[str] = []
    key_messages: list[str] = []
    competitive_position: str | None = None


class ExtractFromTextRequest(BaseModel):
    text: str


async def _verify_client_org(client_id: str, org_id: str) -> None:
    """Raise 404 if client does not belong to the given organization."""
    db = await get_database()
    repo = ClientRepository(db)
    client = await repo.get_by_id(client_id)
    if not client or client.get("organization_id") != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")


@router.get("")
async def get_brand_profile(
    client_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Return the brand profile for a client, or 404 if not set yet."""
    await _verify_client_org(client_id, user.organization_id)
    db = await get_database()
    repo = BrandProfileRepository(db)
    profile = await repo.find_by_client(client_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand profile not found")
    return profile


@router.put("")
async def upsert_brand_profile(
    client_id: str,
    body: BrandProfileUpsertRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Create or update the brand profile for a client."""
    await _verify_client_org(client_id, user.organization_id)
    db = await get_database()
    repo = BrandProfileRepository(db)
    data = body.model_dump(exclude_none=False)
    data["client_id"] = client_id
    data["org_id"] = user.organization_id
    profile_id = await repo.upsert_by_client(client_id, data)
    return {"profile_id": profile_id, "status": "ok"}


@router.post("/extract")
async def extract_brand_profile_endpoint(
    client_id: str,
    user: CurrentUser = Depends(get_current_user),
    text: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
):
    """Extract brand profile fields from pasted text or uploaded file.

    Returns the extracted draft — does NOT save to DB.
    The AE reviews the draft, then calls PUT to save.
    """
    await _verify_client_org(client_id, user.organization_id)

    if file is not None:
        file_bytes = await file.read()
        document_text = parse_file(file_bytes, file.filename or "upload.pdf")
    elif text:
        document_text = text
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide either 'text' or 'file'",
        )

    lang = detect_language(document_text[:500])
    extracted = await extract_brand_profile(document_text, lang)
    return extracted
