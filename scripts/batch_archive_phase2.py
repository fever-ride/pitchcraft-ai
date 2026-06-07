"""
Batch Archive Phase 2 — 9 new campaign documents
=================================================
Same pipeline as batch_archive.py but APPENDS to the existing
scripts/eval_data/archived_records.json rather than overwriting it.

Usage:
    python scripts/batch_archive_phase2.py

Prerequisites (same as batch_archive.py):
    1. MongoDB running:  docker start pitchcraft-mongo-local
    2. Redis running:    docker start <redis-container>
    3. BGE-M3 service:  cd infrastructure/docker/embedding && uvicorn server:app --host 0.0.0.0 --port 8001
    4. ANTHROPIC_API_KEY and PINECONE_API_KEY in .env
"""
import asyncio
import json
import os
import sys
import uuid
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

from backend.core.agents.campaign_extract import extract_campaign_record  # noqa: E402
from backend.core.database.connection import get_database               # noqa: E402
from backend.core.models.campaign_record import ConfirmationStatus      # noqa: E402
from backend.core.rag.campaign_index import index_campaign_propositions  # noqa: E402
from backend.core.rag.parser import parse_file                          # noqa: E402

# ── Config ────────────────────────────────────────────────────────────────────
ORG_ID      = "test-org-001"
CLIENT_ID   = "test-client-001"
OUTPUT_PATH = Path("scripts/eval_data/archived_records.json")

FILES = [
    Path("test_docs/campaign_knowledge/2025雀巢雪咖慕思摇一摇新品咖啡营销推广方案.pptx"),
    Path("test_docs/campaign_knowledge/2026 POWER TRIP 嘉人女性影响力之夜策划案【品牌营销】【奢侈品】.pdf"),
    Path("test_docs/campaign_knowledge/2025小天鹅家电肯德基品牌跨界联动营销方案-28P.pptx"),
    Path("test_docs/campaign_knowledge/IRONMAN健身器械直播间营销方案.pptx"),
    Path("test_docs/campaign_knowledge/百特牛奶x迪卡侬联名中秋国庆双节主题营销传播方案.pptx"),
    Path("test_docs/campaign_knowledge/本田雅阁汽车新媒体运营技巧-账号矩阵（抖音小红书快手）.pptx"),
    Path("test_docs/campaign_knowledge/2026哈啰单车营销产品地图.pdf"),
    Path("test_docs/campaign_knowledge/ETC车宝品牌策略推广方案（车宝APP）.pptx"),
    Path("test_docs/campaign_knowledge/“山水旅情”文化旅游节暨雪浪茶文化节策划方案【文旅】.pdf"),
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
    print("  LLM extraction...", end=" ", flush=True)
    try:
        record = await extract_campaign_record(
            text,
            source_archive_id=f"eval-p2-{idx}",
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
        record_dict["project_id"] = f"eval-p2-project-{idx}"
        record_dict["org_id"] = ORG_ID
        record_dict["source_archive_id"] = f"eval-p2-{idx}"
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
    print("Batch Archive Phase 2 — Campaign KB Eval")
    print(f"ORG_ID: {ORG_ID}  |  Files: {len(FILES)}\n")

    # Verify all files exist
    missing = [f for f in FILES if not f.exists()]
    if missing:
        print("Missing files:")
        for f in missing:
            print(f"  {f}")
        print("\nAborting. Check file paths.")
        return

    print(f"All {len(FILES)} files found. Starting archive pipeline...\n")

    new_results = []
    failed = []

    for i, file_path in enumerate(FILES, start=1):
        result = await archive_one(file_path, i, len(FILES))
        if result:
            new_results.append(result)
            print(f"  ✓ {result['file'][:50]:50s}  id={result['record_id'][:12]}…")
        else:
            failed.append(file_path.name)
            print(f"  ✗ {file_path.name} — FAILED (see above)")

    # Append to existing archived_records.json
    existing = []
    if OUTPUT_PATH.exists():
        existing = json.loads(OUTPUT_PATH.read_text())
    combined = existing + new_results
    OUTPUT_PATH.write_text(json.dumps(combined, ensure_ascii=False, indent=2))

    # Print summary
    print(f"\n{'='*65}")
    print(f"DONE  {len(new_results)}/{len(FILES)} succeeded  |  Total records: {len(combined)}")
    print(f"{'='*65}\n")

    if failed:
        print(f"Failed ({len(failed)}):")
        for f in failed:
            print(f"  ✗ {f}")
        print()

    print("New records:")
    print(f"{'File':45s}  {'record_id':36s}  industry")
    print(f"{'─'*45}  {'─'*36}  {'─'*20}")
    for r in new_results:
        fid = r["record_id"]
        print(f"  {r['file'][:43]:43s}  {fid}  {r['industry'] or '?'}")

    print(f"\nFull record list saved to: {OUTPUT_PATH}")
    print("\n⚠  Next step: add 2 queries per new record to scripts/eval_data/query_set.json")
    print("   Then run: python scripts/eval_retrieval.py")


if __name__ == "__main__":
    asyncio.run(main())
