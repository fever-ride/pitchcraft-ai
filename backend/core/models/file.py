from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class FileCategory(str, Enum):
    BRAND_LIBRARY = "brand_library"
    PROJECT_LIBRARY = "project_library"


class FileType(str, Enum):
    BRAND_SPEC = "brand_spec"
    BRAND_HISTORY_PROPOSAL = "brand_history_proposal"
    BRAND_HISTORY_COPY = "brand_history_copy"
    PROJECT_BRIEF = "project_brief"
    COMPETITOR_COPY = "competitor_copy"
    VISUAL_REF = "visual_ref"


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class FileRecord(BaseModel):
    id: str | None = Field(None, alias="_id")
    client_id: str
    project_id: str | None = None
    uploaded_by: str
    filename: str
    storage_path: str | None = None
    file_category: FileCategory
    file_type: FileType
    pinecone_namespace: str | None = None
    chunk_count: int = 0
    processing_status: ProcessingStatus = ProcessingStatus.PENDING
    processing_error: str | None = None
    deleted: bool = False
    deleted_at: datetime | None = None
    deleted_by: str | None = None
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
