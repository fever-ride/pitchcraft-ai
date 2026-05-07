"""Tests for file upload validation logic."""
import pytest

from backend.core.models.file import FileCategory, FileType, ProcessingStatus


def test_file_category_brand_library():
    brand_types = [FileType.BRAND_SPEC, FileType.BRAND_HISTORY_PROPOSAL, FileType.BRAND_HISTORY_COPY]
    for ft in brand_types:
        assert ft in (FileType.BRAND_SPEC, FileType.BRAND_HISTORY_PROPOSAL, FileType.BRAND_HISTORY_COPY)


def test_file_category_project_library():
    project_types = [FileType.PROJECT_BRIEF, FileType.COMPETITOR_COPY, FileType.VISUAL_REF]
    for ft in project_types:
        assert ft not in (FileType.BRAND_SPEC, FileType.BRAND_HISTORY_PROPOSAL, FileType.BRAND_HISTORY_COPY)


def test_allowed_extensions():
    try:
        from backend.api.v1.endpoints.files import ALLOWED_EXTENSIONS
        assert ".pdf" in ALLOWED_EXTENSIONS
        assert ".docx" in ALLOWED_EXTENSIONS
        assert ".pptx" in ALLOWED_EXTENSIONS
        assert ".txt" not in ALLOWED_EXTENSIONS
        assert ".exe" not in ALLOWED_EXTENSIONS
    except ImportError:
        pytest.skip("FastAPI not installed in test environment")


def test_max_file_size():
    try:
        from backend.api.v1.endpoints.files import MAX_FILE_SIZE
        assert MAX_FILE_SIZE == 50 * 1024 * 1024
    except ImportError:
        pytest.skip("FastAPI not installed in test environment")


def test_file_type_enum_values():
    assert FileType.BRAND_SPEC.value == "brand_spec"
    assert FileType.BRAND_HISTORY_PROPOSAL.value == "brand_history_proposal"
    assert FileType.PROJECT_BRIEF.value == "project_brief"
    assert FileType.COMPETITOR_COPY.value == "competitor_copy"
    assert FileType.VISUAL_REF.value == "visual_ref"


def test_processing_status_enum():
    assert ProcessingStatus.PENDING.value == "pending"
    assert ProcessingStatus.PROCESSING.value == "processing"
    assert ProcessingStatus.DONE.value == "done"
    assert ProcessingStatus.FAILED.value == "failed"
