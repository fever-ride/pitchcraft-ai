"""
Batch Archive — Campaign Knowledge Base Eval Setup
===================================================
Archives multiple campaign documents into the knowledge base.
Runs the full pipeline for each file:
  parse → LLM extract → MongoDB store → auto-confirm → propositions → Pinecone upsert

Records are kept permanently (no cleanup). Record IDs are saved to
scripts/eval_data/archived_records.json for use in eval scripts.

Usage:
    python scripts/batch_archive.py

Prerequisites (same as test_campaign_kb_pipeline.py):
    1. MongoDB running:  docker start pitchcraft-mongo-local
    2. Redis running:    docker start <redis-container> OR docker run -d -p 6379:6379 redis:7-alpine
    3. BGE-M3 service:  cd infrastructure/docker/embedding && uvicorn server:app --host 0.0.0.0 --port 8001
    4. ANTHROPIC_API_KEY and PINECONE_API_KEY in .env
"""
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

# Load .env and override service URLs before any backend imports
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

from backend.core.agents.campaign_extract import extract_campaign_record  # noqa: E402
from backend.core.database.connection import get_database  # noqa: E402
from backend.core.models.campaign_record import ConfirmationStatus  # noqa: E402
from backend.core.rag.campaign_index import index_campaign_propositions  # noqa: E402
from backend.core.rag.parser import parse_file  # noqa: E402

# ── Config ────────────────────────────────────────────────────────────────────
ORG_ID = "test-org-001"
CLIENT_ID = "test-client-001"
OUTPUT_PATH = Path("scripts/eval_data/archived_records.json")

FILES = [
    Path("test_docs/campaign_knowledge/安踏24Q3【中国甲】营销结案.pdf"),
    Path("test_docs/campaign_knowledge/MINI汽车品牌全年年度营销方案.pdf"),
    Path("test_docs/campaign_knowledge/美团外卖「外卖黄的更灵的」整合营销方案.pdf"),
    Path("test_docs/campaign_knowledge/COSTA全新罐装咖啡新品上市跨界整合营销.pdf"),
    Path("test_docs/campaign_knowledge/popchrio欧可芮小红书营销方案.pdf"),
    Path("test_docs/campaign_knowledge/Stokke成长椅产品爆品复盘.pdf"),
]
# ─────────────────────────────────────────────────────────────────────────────


async def archive_one(file_path: Path, idx: int, total: int) -> dict | None:
    """Full pipeline for one document. Returns record info dict or None on failure."""
    label = f"[{idx}/{total}] {file_path.name}"
    print(f"\n{'─'*65}")
    print(f"{label}")
    print(f"{'─'*65}")

    # 1. Parse
    print("  Parsing...", end=" ", flush=True)
    try:
        file_bytes = file_path.read_bytes()
        text = parse_file(file_bytes, file_path.name)
        print(f"{len(text):,} chars")
    except Exception as e:
        print(f"FAILED: {e}")
        return None

    if not text.strip():
        print("  Empty text after parse — skipping")
        return None

    # 2. LLM Extraction
    print("  LLM extraction (2-3 parallel calls)...", end=" ", flush=True)
    try:
        record = await extract_campaign_record(
            text,
            source_archive_id=f"eval-archive-{idx}",
            page_count=None,
        )
        print(f"done  [{record.record_type.value} | {record.confidence.value}]")
    except Exception as e:
        print(f"FAILED: {e}")
        return None

    meta = record.meta
    print(f"  → {meta.client_name or '?'} | {meta.industry or '?'} | {meta.campaign_type or '?'}")
    if meta.campaign_subtype:
        print(f"    subtype: {meta.campaign_subtype}")

    # 3. Store in MongoDB
    print("  Storing in MongoDB...", end=" ", flush=True)
    try:
        db = await get_database()
        record_id = str(uuid.uuid4())
        record_dict = record.model_dump(by_alias=True)
        record_dict["_id"] = record_id
        record_dict["client_id"] = CLIENT_ID
        record_dict["project_id"] = f"eval-project-{idx}"
        record_dict["org_id"] = ORG_ID
        record_dict["source_archive_id"] = f"eval-archive-{idx}"
        await db["campaign_records"].insert_one(record_dict)
        print(f"record_id={record_id[:12]}…")
    except Exception as e:
        print(f"FAILED: {e}")
        return None

    # 4. Auto-confirm
    print("  Auto-confirming...", end=" ", flush=True)
    try:
        await db["campaign_records"].update_one(
            {"_id": record_id},
            {"$set": {
                "status": ConfirmationStatus.CONFIRMED.value,
                "confirmed_by": "eval-script",
            }},
        )
        confirmed_doc = await db["campaign_records"].find_one({"_id": record_id})
        print("confirmed")
    except Exception as e:
        print(f"FAILED: {e}")
        return None

    # 5. Proposition extraction + Pinecone upsert
    print("  Extracting propositions + indexing to Pinecone...", end=" ", flush=True)
    try:
        n = await index_campaign_propositions(record_id, confirmed_doc, ORG_ID)
        print(f"{n} propositions indexed")
    except Exception as e:
        print(f"FAILED (propositions): {e}")
        # Don't return None — record is in MongoDB, user can re-index later
        n = 0

    return {
        "file": file_path.name,
        "record_id": record_id,
        "client_name": meta.client_name,
        "industry": meta.industry,
        "campaign_type": str(meta.campaign_type.value) if meta.campaign_type else None,
        "campaign_subtype": meta.campaign_subtype,
        "record_type": record.record_type.value,
        "confidence": record.confidence.value,
        "propositions_indexed": n,
    }


async def main():
    print("Batch Archive — Campaign KB Eval Setup")
    print(f"ORG_ID: {ORG_ID}  |  Files: {len(FILES)}\n")

    # Verify all files exist before starting
    missing = [f for f in FILES if not f.exists()]
    if missing:
        print("Missing files:")
        for f in missing:
            print(f"  {f}")
        print("\nAborting. Check file paths.")
        return

    print(f"All {len(FILES)} files found. Starting archive pipeline...\n")

    results = []
    failed = []

    for i, file_path in enumerate(FILES, start=1):
        result = await archive_one(file_path, i, len(FILES))
        if result:
            results.append(result)
            print(f"  ✓ {result['file'][:50]:50s}  id={result['record_id'][:12]}…")
        else:
            failed.append(file_path.name)
            print(f"  ✗ {file_path.name} — FAILED (see above)")

    # Save results
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Print summary
    print(f"\n{'='*65}")
    print(f"DONE  {len(results)}/{len(FILES)} succeeded")
    print(f"{'='*65}\n")

    print("Archived records:")
    print(f"{'File':45s}  {'record_id':36s}  industry")
    print(f"{'─'*45}  {'─'*36}  {'─'*20}")
    for r in results:
        print(f"{r['file'][:45]:45s}  {r['record_id']}  {r['industry'] or '?'}")

    if failed:
        print(f"\nFailed: {failed}")

    print(f"\nRecord IDs saved to: {OUTPUT_PATH}")
    print("\nNext step:")
    print("  Fill these record_ids into scripts/eval_data/query_set.json")
    print("  then run: python scripts/eval_retrieval.py")

    # Also print mapping for easy copy-paste into query_set.json
    print(f"\n{'─'*65}")
    print("Copy-paste mapping for query_set.json:")
    print(f"{'─'*65}")
    name_map = {
        "安踏": "ANTA_ID",
        "MINI": "MINI_ID",
        "美团": "MEITUAN_ID",
        "COSTA": "COSTA_ID",
        "popchrio": "POPCHRIO_ID",
        "Stokke": "STOKKE_ID",
    }
    for r in results:
        placeholder = next((v for k, v in name_map.items() if k.lower() in r["file"].lower()), r["file"][:10])
        print(f'  "{placeholder}": "{r["record_id"]}"')


if __name__ == "__main__":
    asyncio.run(main())
