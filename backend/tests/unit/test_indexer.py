"""Tests for Pinecone namespace resolution logic (no external deps)."""
from backend.core.models.file import FileType


def resolve_namespace(file_type: str, client_id: str, project_id: str | None) -> str:
    """Mirror of indexer.resolve_namespace for testing without pinecone import."""
    if file_type == FileType.BRAND_SPEC:
        return f"brand_spec_{client_id}"
    if file_type in (FileType.BRAND_HISTORY_PROPOSAL, FileType.BRAND_HISTORY_COPY):
        return f"brand_style_{client_id}"
    return f"project_{project_id or client_id}"


def test_brand_spec_namespace():
    ns = resolve_namespace("brand_spec", "client_abc", None)
    assert ns == "brand_spec_client_abc"


def test_brand_history_proposal_namespace():
    ns = resolve_namespace("brand_history_proposal", "client_abc", None)
    assert ns == "brand_style_client_abc"


def test_brand_history_copy_namespace():
    ns = resolve_namespace("brand_history_copy", "client_abc", None)
    assert ns == "brand_style_client_abc"


def test_project_file_with_project_id():
    ns = resolve_namespace("project_brief", "client_abc", "proj_123")
    assert ns == "project_proj_123"


def test_project_file_without_project_id_falls_back_to_client():
    ns = resolve_namespace("project_brief", "client_abc", None)
    assert ns == "project_client_abc"


def test_competitor_copy_namespace():
    ns = resolve_namespace("competitor_copy", "client_abc", "proj_123")
    assert ns == "project_proj_123"


# --- Resource namespace resolution ---

def resource_namespace(resource_type: str, client_id: str) -> str:
    """Mirror of models.resource.resource_namespace."""
    type_map = {
        "kol": "resource_kol",
        "koc": "resource_kol",
        "media": "resource_media",
        "vendor": "resource_vendor",
        "placement": "resource_placement",
    }
    prefix = type_map.get(resource_type, "resource_kol")
    return f"{prefix}_{client_id}"


def test_resource_kol_namespace():
    assert resource_namespace("kol", "client_x") == "resource_kol_client_x"


def test_resource_koc_shares_kol_namespace():
    assert resource_namespace("koc", "client_x") == "resource_kol_client_x"


def test_resource_media_namespace():
    assert resource_namespace("media", "client_x") == "resource_media_client_x"


def test_resource_vendor_namespace():
    assert resource_namespace("vendor", "client_x") == "resource_vendor_client_x"


def test_resource_placement_namespace():
    assert resource_namespace("placement", "client_x") == "resource_placement_client_x"


def test_resource_unknown_type_defaults_to_kol():
    assert resource_namespace("unknown", "client_x") == "resource_kol_client_x"
