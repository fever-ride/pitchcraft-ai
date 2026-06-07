"""
reindex_all_records.py — Re-index propositions for all 14 archived records.

Use after updating proposition extraction logic (prompt rules, meta prefix, etc.)
to propagate the changes to all existing records in the KB.

Steps per record:
  1. Fetch current record from MongoDB
  2. Delete old propositions (MongoDB campaign_propositions collection)
  3. Delete old vectors (Pinecone, filtered by campaign_record_id)
  4. Re-extract and re-index with updated prompt/prefix
  5. Update propositions_indexed count in archived_records.json

Usage:
    python scripts/reindex_all_records.py

Prerequisites:
    1. Services running: MongoDB, Redis, BGE-M3 embedding service, Pinecone configured
    2. scripts/eval_data/archived_records.json exists and has all record IDs
"""
import asyncio
import json
import os
import sys
from pathlib import Path

# Load .env (force-override so ANTHROPIC_API_KEY is always set correctly)
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    with open(_env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ[_k.strip()] = _v.strip()

os.environ["MONGODB_URL"] = "mongodb://localhost:27017"
os.environ["EMBEDDING_SERVICE_URL"] = "http://localhost:8001"

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.database.connection import get_database                   # noqa: E402
from backend.core.rag.campaign_index import index_campaign_propositions     # noqa: E402
from backend.core.rag.indexer import _get_index                             # noqa: E402

ORG_ID = "test-org-001"
ARCHIVED_RECORDS_PATH = Path("scripts/eval_data/archived_records.json")


async def reindex_record(
    record_id: str,
    client_name: str,
    db,
    pinecone_index,
    namespace: str,
) -> int:
    """Delete old propositions/vectors and re-index one record. Returns new prop count."""

    # 1. Fetch current record from MongoDB
    doc = await db["campaign_records"].find_one({"_id": record_id})
    if not doc:
        print(f"  ✗ {record_id[:8]}… NOT FOUND in MongoDB — skipping")
        return -1

    # 2. Delete old propositions from MongoDB
    del_mongo = await db["campaign_propositions"].delete_many(
        {"campaign_record_id": record_id}
    )

    # 3. Delete old vectors from Pinecone
    try:
        pinecone_index.delete(
            filter={"campaign_record_id": {"$eq": record_id}},
            namespace=namespace,
        )
        pinecone_ok = True
    except Exception as e:
        print(f"  ⚠  Pinecone delete warning for {record_id[:8]}…: {e}")
        pinecone_ok = False

    # 4. Re-extract and re-index
    count = await index_campaign_propositions(record_id, doc, ORG_ID)

    status = "✓" if count > 0 else "✗"
    print(
        f"  {status} {record_id[:8]}… ({client_name})"
        f"  old_props={del_mongo.deleted_count}"
        f"  pinecone={'ok' if pinecone_ok else 'warn'}"
        f"  new_props={count}"
    )
    return count


async def main():
    if not ARCHIVED_RECORDS_PATH.exists():
        print(f"ERROR: {ARCHIVED_RECORDS_PATH} not found")
        return

    archived = json.loads(ARCHIVED_RECORDS_PATH.read_text())
    print(f"Loaded {len(archived)} records from {ARCHIVED_RECORDS_PATH}\n")

    db = await get_database()
    pinecone_index = _get_index()
    namespace = f"campaign_knowledge_{ORG_ID}"

    print(f"ORG_ID={ORG_ID}  namespace={namespace}")
    print("─" * 60)

    results = {}
    for entry in archived:
        record_id = entry["record_id"]
        client_name = entry.get("client_name", "?")
        count = await reindex_record(
            record_id=record_id,
            client_name=client_name,
            db=db,
            pinecone_index=pinecone_index,
            namespace=namespace,
        )
        results[record_id] = count

    # Update propositions_indexed in archived_records.json
    updated = 0
    for entry in archived:
        rid = entry["record_id"]
        if rid in results and results[rid] >= 0:
            entry["propositions_indexed"] = results[rid]
            updated += 1

    ARCHIVED_RECORDS_PATH.write_text(
        json.dumps(archived, ensure_ascii=False, indent=2)
    )

    # Summary
    total_props = sum(v for v in results.values() if v >= 0)
    success = sum(1 for v in results.values() if v > 0)
    failed = sum(1 for v in results.values() if v <= 0)

    print("─" * 60)
    print(f"\nDone. {success}/{len(archived)} records re-indexed successfully.")
    if failed:
        print(f"  ✗ {failed} record(s) failed (count=0 or not found in MongoDB)")
    print(f"  Total propositions indexed: {total_props}")
    print(f"  Updated {updated} entries in {ARCHIVED_RECORDS_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
