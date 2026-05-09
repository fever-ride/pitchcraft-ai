"""Resource Excel import: parse .xlsx, create DB records, embed, upsert to Pinecone."""
import io
from collections import defaultdict
from datetime import datetime

from openpyxl import load_workbook

from backend.core.database.connection import get_database
from backend.core.models.resource import ResourceStatus, parse_follower_count, resource_namespace
from backend.core.rag.embedder import embed_texts
from backend.core.rag.indexer import upsert_vectors

VALID_TYPES = {"kol", "koc", "media", "vendor", "placement"}


def parse_resource_excel(file_bytes: bytes) -> list[dict]:
    """Parse xlsx bytes into list of resource dicts."""
    wb = load_workbook(io.BytesIO(file_bytes), read_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []

    headers = [str(h).strip().lower() if h else "" for h in rows[0]]
    resources = []

    for row in rows[1:]:
        if not any(row):
            continue
        record = {}
        for idx, header in enumerate(headers):
            val = row[idx] if idx < len(row) else None
            if val is not None:
                record[header] = str(val).strip()
        if record.get("name"):
            record.setdefault("type", "kol")
            record.setdefault("platform", "")
            record.setdefault("tags", "")
            record["followers_count"] = parse_follower_count(record.get("followers"))
            record["status"] = ResourceStatus.ACTIVE.value
            record["last_verified_at"] = datetime.utcnow()
            resources.append(record)

    wb.close()
    return resources


def _resource_to_text(r: dict) -> str:
    """Convert resource dict to searchable text for embedding."""
    parts = [
        f"Name: {r.get('name', '')}",
        f"Type: {r.get('type', '')}",
    ]
    if r.get("platform"):
        parts.append(f"Platform: {r['platform']}")
    if r.get("followers"):
        parts.append(f"Followers: {r['followers']}")
    if r.get("tags"):
        parts.append(f"Tags: {r['tags']}")
    if r.get("pricing"):
        parts.append(f"Pricing: {r['pricing']}")
    if r.get("notes"):
        parts.append(f"Notes: {r['notes']}")
    # Media-specific
    if r.get("outlet_type"):
        parts.append(f"Outlet: {r['outlet_type']}")
    if r.get("beat"):
        parts.append(f"Beat: {r['beat']}")
    # Vendor-specific
    if r.get("service_type"):
        parts.append(f"Service: {r['service_type']}")
    if r.get("region"):
        parts.append(f"Region: {r['region']}")
    # Placement-specific
    if r.get("placement_type"):
        parts.append(f"Placement: {r['placement_type']}")
    if r.get("location"):
        parts.append(f"Location: {r['location']}")
    if r.get("audience_reach"):
        parts.append(f"Reach: {r['audience_reach']}")
    return " | ".join(parts)


async def import_resources(file_bytes: bytes, client_id: str) -> dict:
    """Full import pipeline: parse → DB → embed → Pinecone (grouped by type)."""
    resources = parse_resource_excel(file_bytes)
    if not resources:
        return {"imported": 0, "error": "No valid rows found"}

    db = await get_database()
    collection = db["resources"]

    for r in resources:
        r["client_id"] = client_id
        await collection.insert_one(r)

    # Group by type for namespace-specific upsert
    by_type: dict[str, list[dict]] = defaultdict(list)
    for r in resources:
        rtype = r.get("type", "kol").lower()
        if rtype not in VALID_TYPES:
            rtype = "kol"
        by_type[rtype].append(r)

    namespaces_used = []
    for rtype, group in by_type.items():
        ns = resource_namespace(rtype, client_id)
        texts = [_resource_to_text(r) for r in group]
        embeddings = await embed_texts(texts)
        batch_id = f"import_{client_id}_{rtype}_{len(group)}"
        upsert_vectors(namespace=ns, file_id=batch_id, chunks=texts, embeddings=embeddings)
        namespaces_used.append(ns)

    return {
        "imported": len(resources),
        "by_type": {k: len(v) for k, v in by_type.items()},
        "namespaces": namespaces_used,
    }
