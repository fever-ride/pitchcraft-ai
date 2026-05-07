"""Resource Excel import: parse .xlsx, create DB records, embed, upsert to Pinecone."""
import io
import json

from openpyxl import load_workbook

from backend.core.database.connection import get_database
from backend.core.rag.embedder import embed_texts
from backend.core.rag.indexer import upsert_vectors

EXPECTED_COLUMNS = {"name", "type", "platform", "followers", "tags", "pricing", "notes"}


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
            resources.append(record)

    wb.close()
    return resources


def _resource_to_text(r: dict) -> str:
    """Convert resource dict to searchable text for embedding."""
    parts = [
        f"Name: {r.get('name', '')}",
        f"Type: {r.get('type', '')}",
        f"Platform: {r.get('platform', '')}",
    ]
    if r.get("followers"):
        parts.append(f"Followers: {r['followers']}")
    if r.get("tags"):
        parts.append(f"Tags: {r['tags']}")
    if r.get("pricing"):
        parts.append(f"Pricing: {r['pricing']}")
    if r.get("notes"):
        parts.append(f"Notes: {r['notes']}")
    return " | ".join(parts)


async def import_resources(file_bytes: bytes, client_id: str) -> dict:
    """Full import pipeline: parse → DB → embed → Pinecone."""
    resources = parse_resource_excel(file_bytes)
    if not resources:
        return {"imported": 0, "error": "No valid rows found"}

    db = await get_database()
    collection = db["resources"]

    db_ids = []
    for r in resources:
        r["client_id"] = client_id
        result = await collection.insert_one(r)
        db_ids.append(str(result.inserted_id))

    texts = [_resource_to_text(r) for r in resources]
    embeddings = await embed_texts(texts)

    namespace = f"resource_kol_{client_id}"
    batch_id = f"import_{client_id}_{len(resources)}"
    upsert_vectors(
        namespace=namespace,
        file_id=batch_id,
        chunks=texts,
        embeddings=embeddings,
    )

    return {"imported": len(resources), "namespace": namespace}
