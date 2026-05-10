import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from backend.api.v1.permissions import CurrentUser, Role, get_current_user
from backend.core.config import settings
from backend.core.database.connection import get_database
from backend.core.database.repositories.files import FileRepository
from backend.core.models.file import FileCategory, FileType, ProcessingStatus
from backend.core.rag.process import process_file_task
from backend.core.rag.visual_process import process_visual_file_task

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".ppt"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
CHUNK_SIZE = 64 * 1024  # 64 KB streaming chunks


def _get_category(file_type: FileType) -> FileCategory:
    if file_type in (FileType.BRAND_SPEC, FileType.BRAND_HISTORY_PROPOSAL, FileType.BRAND_HISTORY_COPY):
        return FileCategory.BRAND_LIBRARY
    return FileCategory.PROJECT_LIBRARY


async def _stream_to_disk(upload: UploadFile, dest: Path) -> int:
    """Stream uploaded file to disk in chunks. Returns total bytes written."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with open(dest, "wb") as f:
        while chunk := await upload.read(CHUNK_SIZE):
            total += len(chunk)
            if total > MAX_FILE_SIZE:
                dest.unlink(missing_ok=True)
                raise HTTPException(status_code=400, detail="File exceeds 50 MB limit")
            f.write(chunk)
    return total


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_file(
    file: UploadFile = File(...),
    client_id: str = Form(...),
    project_id: str | None = Form(None),
    file_type: str = Form(...),
    user: CurrentUser = Depends(get_current_user),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    try:
        ft = FileType(file_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid file_type: {file_type}")

    storage_key = f"{client_id}/{uuid.uuid4().hex}{ext}"
    storage_path = Path(settings.file_storage_dir) / storage_key
    await _stream_to_disk(file, storage_path)

    db = await get_database()
    repo = FileRepository(db)

    record = {
        "client_id": client_id,
        "project_id": project_id,
        "uploaded_by": user.user_id,
        "filename": file.filename,
        "file_category": _get_category(ft).value,
        "file_type": ft.value,
        "storage_path": str(storage_path),
        "processing_status": ProcessingStatus.PENDING.value,
        "chunk_count": 0,
        "deleted": False,
        "uploaded_at": datetime.utcnow(),
    }

    file_id = await repo.create(record)

    client_doc = await db.clients.find_one({"_id": client_id}, {"name": 1})
    client_name = client_doc.get("name") if client_doc else None

    if ft == FileType.VISUAL_REF:
        process_visual_file_task.delay(
            file_id=file_id,
            storage_path=str(storage_path),
            filename=file.filename,
            client_id=client_id,
        )
    else:
        process_file_task.delay(
            file_id=file_id,
            storage_path=str(storage_path),
            filename=file.filename,
            file_type=ft.value,
            client_id=client_id,
            project_id=project_id,
            client_name=client_name,
        )

    return {"status": "processing", "file_id": file_id}


@router.get("")
async def list_files(
    client_id: str | None = None,
    project_id: str | None = None,
    user: CurrentUser = Depends(get_current_user),
):
    db = await get_database()
    repo = FileRepository(db)

    if project_id:
        files = await repo.find_by_project(project_id)
    elif client_id:
        files = await repo.find_by_client(client_id)
    else:
        files = []

    return files


@router.get("/{file_id}")
async def get_file(file_id: str, user: CurrentUser = Depends(get_current_user)):
    db = await get_database()
    repo = FileRepository(db)
    doc = await repo.get_by_id(file_id)
    if not doc or doc.get("deleted"):
        raise HTTPException(status_code=404, detail="File not found")
    return doc


@router.delete("/{file_id}")
async def delete_file(file_id: str, user: CurrentUser = Depends(get_current_user)):
    db = await get_database()
    repo = FileRepository(db)
    doc = await repo.get_by_id(file_id)

    if not doc or doc.get("deleted"):
        raise HTTPException(status_code=404, detail="File not found")

    is_brand_lib = doc.get("file_category") == FileCategory.BRAND_LIBRARY.value
    if is_brand_lib and user.role not in (Role.LEAD_ACCOUNT, Role.ADMIN):
        raise HTTPException(status_code=403, detail="Only lead_account+ can delete Brand Library files")

    await repo.soft_delete(file_id, user.user_id)
    return {"status": "deleted"}
