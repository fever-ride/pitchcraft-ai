"""Tests for Pinecone namespace resolution logic (no external deps)."""
from backend.core.models.file import FileType


def resolve_namespace(file_type: str, client_id: str, project_id: str | None) -> str:
    """Mirror of indexer.resolve_namespace for testing without pinecone import."""
    if file_type in (FileType.BRAND_SPEC, FileType.BRAND_HISTORY_PROPOSAL, FileType.BRAND_HISTORY_COPY):
        prefix = "brand_spec" if file_type == FileType.BRAND_SPEC else "brand_history"
        return f"{prefix}_{client_id}"
    return f"project_{project_id or client_id}"


def test_brand_spec_namespace():
    ns = resolve_namespace("brand_spec", "client_abc", None)
    assert ns == "brand_spec_client_abc"


def test_brand_history_proposal_namespace():
    ns = resolve_namespace("brand_history_proposal", "client_abc", None)
    assert ns == "brand_history_client_abc"


def test_brand_history_copy_namespace():
    ns = resolve_namespace("brand_history_copy", "client_abc", None)
    assert ns == "brand_history_client_abc"


def test_project_file_with_project_id():
    ns = resolve_namespace("project_brief", "client_abc", "proj_123")
    assert ns == "project_proj_123"


def test_project_file_without_project_id_falls_back_to_client():
    ns = resolve_namespace("project_brief", "client_abc", None)
    assert ns == "project_client_abc"


def test_competitor_copy_namespace():
    ns = resolve_namespace("competitor_copy", "client_abc", "proj_123")
    assert ns == "project_proj_123"
