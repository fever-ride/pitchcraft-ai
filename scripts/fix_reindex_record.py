"""
fix_reindex_record.py — Patch meta fields and re-index propositions for one record.

Usage:
    python scripts/fix_reindex_record.py

Hardcoded to fix popchrio (dfeccd49-…):
  - Sets meta.industry = "美妆护肤"
  - Sets meta.client_name = "欧可芮(popchrio)"
  - Deletes old propositions (MongoDB + Pinecone)
  - Re-extracts and re-indexes with updated meta prefix
"""
import asyncio
import os
import sys
from pathlib import Path

# Load .env
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

from backend.core.database.connection import get_database          # noqa: E402
from backend.core.rag.campaign_index import index_campaign_propositions  # noqa: E402
from backend.core.rag.indexer import _get_index                    # noqa: E402

RECORD_ID = "dfeccd49-dd82-4249-8d3b-ad45f7d2af96"
ORG_ID    = "test-org-001"

# Fields to patch
PATCH = {
    "meta.industry":    "美妆护肤",
    "meta.client_name": "欧可芮(popchrio)",
}


async def main():
    db = await get_database()

    # 1. Fetch current record
    doc = await db["campaign_records"].find_one({"_id": RECORD_ID})
    if not doc:
        print(f"ERROR: record {RECORD_ID} not found in MongoDB")
        return

    print(f"Record found: {doc.get('_id')} | current industry={doc.get('meta', {}).get('industry')}")

    # 2. Patch meta fields in MongoDB
    result = await db["campaign_records"].update_one(
        {"_id": RECORD_ID},
        {"$set": PATCH},
    )
    print(f"Patched meta: {PATCH}  (matched={result.matched_count}, modified={result.modified_count})")

    # 3. Delete old propositions from MongoDB
    del_result = await db["campaign_propositions"].delete_many({"campaign_record_id": RECORD_ID})
    print(f"Deleted {del_result.deleted_count} old propositions from MongoDB")

    # 4. Delete old vectors from Pinecone
    namespace = f"campaign_knowledge_{ORG_ID}"
    try:
        index = _get_index()
        index.delete(
            filter={"campaign_record_id": {"$eq": RECORD_ID}},
            namespace=namespace,
        )
        print(f"Deleted old vectors from Pinecone namespace={namespace}")
    except Exception as e:
        print(f"Pinecone delete warning (non-fatal): {e}")

    # 5. Re-fetch patched record and re-index
    updated_doc = await db["campaign_records"].find_one({"_id": RECORD_ID})
    print(f"\nRe-indexing with updated meta: industry={updated_doc.get('meta', {}).get('industry')}")

    count = await index_campaign_propositions(RECORD_ID, updated_doc, ORG_ID)
    print(f"✓ Re-indexed {count} propositions for {RECORD_ID[:8]}…")

    # 6. Update archived_records.json
    import json
    ar_path = Path("scripts/eval_data/archived_records.json")
    if ar_path.exists():
        records = json.loads(ar_path.read_text())
        for r in records:
            if r.get("record_id") == RECORD_ID:
                r["industry"] = "美妆护肤"
                r["client_name"] = "欧可芮(popchrio)"
                r["propositions_indexed"] = count
        ar_path.write_text(json.dumps(records, ensure_ascii=False, indent=2))
        print(f"Updated archived_records.json")


if __name__ == "__main__":
    asyncio.run(main())
