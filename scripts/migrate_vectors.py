"""Re-process existing files with contextual embedding and adaptive chunking.

This script re-runs the file processing pipeline for all successfully processed
files, replacing their Pinecone vectors with the new format:
  - Contextual prefix (client | file_type | filename | page/slide)
  - Source location metadata (page_number, slide_index, filename)
  - Adaptive chunk sizing by file_type

Usage:
    python scripts/migrate_vectors.py [--dry-run] [--client-id CLIENT_ID]

Options:
    --dry-run       Show what would be reprocessed without actually doing it
    --client-id     Only migrate files for a specific client
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.database.connection import get_database
from backend.core.rag.process import _process_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def migrate(dry_run: bool = False, client_id: str | None = None):
    db = await get_database()
    files_col = db.files

    query = {"processing_status": "done", "deleted": False, "chunk_count": {"$gt": 0}}
    if client_id:
        query["client_id"] = client_id

    cursor = files_col.find(query)
    files = await cursor.to_list(length=None)

    logger.info(f"Found {len(files)} files to migrate")

    if dry_run:
        for f in files:
            logger.info(f"  [DRY RUN] Would reprocess: {f.get('filename')} (client={f.get('client_id')}, type={f.get('file_type')})")
        return

    # Look up client names for contextual prefix
    client_ids = list(set(f.get("client_id") for f in files if f.get("client_id")))
    clients_cursor = db.clients.find({"_id": {"$in": client_ids}}, {"name": 1})
    clients = await clients_cursor.to_list(length=None)
    client_names = {str(c["_id"]): c.get("name") for c in clients}

    success = 0
    failed = 0

    for f in files:
        file_id = str(f["_id"])
        storage_path = f.get("storage_path")
        filename = f.get("filename", "")
        file_type = f.get("file_type", "")
        cid = f.get("client_id", "")
        project_id = f.get("project_id")
        client_name = client_names.get(cid)

        if not storage_path or not Path(storage_path).exists():
            logger.warning(f"  Skipping {filename} ({file_id}): file not on disk")
            failed += 1
            continue

        try:
            await _process_file(
                file_id=file_id,
                storage_path=storage_path,
                filename=filename,
                file_type=file_type,
                client_id=cid,
                project_id=project_id,
                client_name=client_name,
            )
            success += 1
            logger.info(f"  Migrated: {filename} ({file_id})")
        except Exception as e:
            failed += 1
            logger.error(f"  Failed: {filename} ({file_id}): {e}")

    logger.info(f"Migration complete: {success} succeeded, {failed} failed")


def main():
    parser = argparse.ArgumentParser(description="Re-embed existing files with contextual prefix and source tracking")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be reprocessed")
    parser.add_argument("--client-id", type=str, default=None, help="Only migrate files for this client")
    args = parser.parse_args()

    asyncio.run(migrate(dry_run=args.dry_run, client_id=args.client_id))


if __name__ == "__main__":
    main()
