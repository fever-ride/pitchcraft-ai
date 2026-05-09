from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from backend.api.v1.permissions import CurrentUser, Role, get_current_user
from backend.core.database.connection import get_database
from backend.core.database.repositories.files import FileRepository
from backend.core.models.file import FileCategory, FileType, ProcessingStatus
from backend.core.rag.process import process_file_task
from backend.core.rag.visual_process import process_visual_file_task

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".ppt"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def _get_category(file_type: FileType) -> FileCategory:
    if file_type in (FileType.BRAND_SPEC, FileType.BRAND_HISTORY_PROPOSAL, FileType.BRAND_HISTORY_COPY):
        return FileCategory.BRAND_LIBRARY
    return FileCategory.PROJECT_LIBRARY


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_file(
    file: UploadFile = File(...),
    client_id: str = Form(...),
    project_id: str | None = Form(None),
    file_type: str = Form(...),
    user: CurrentUser = Depends(get_current_user),
):
    from pathlib import Path

    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    try:
        ft = FileType(file_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid file_type: {file_type}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 50 MB limit")

    db = await get_database()
    repo = FileRepository(db)

    record = {
        "client_id": client_id,
        "project_id": project_id,
        "uploaded_by": user.user_id,
        "filename": file.filename,
        "file_category": _get_category(ft).value,
        "file_type": ft.value,
        "processing_status": ProcessingStatus.PENDING.value,
        "chunk_count": 0,
        "deleted": False,
        "uploaded_at": datetime.utcnow(),
    }

    file_id = await repo.create(record)

    if ft == FileType.VISUAL_REF:
        process_visual_file_task.delay(
            file_id=file_id,
            file_bytes_hex=content.hex(),
            filename=file.filename,
            client_id=client_id,
        )
    else:
        process_file_task.delay(
            file_id=file_id,
            file_bytes_hex=content.hex(),
            filename=file.filename,
            file_type=ft.value,
            client_id=client_id,
            project_id=project_id,
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
