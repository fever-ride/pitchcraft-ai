"""Project archive processing: parse report → extract → distribute to multiple stores."""
import asyncio
import logging
import uuid
from pathlib import Path

from backend.core.agents.archive import extract_archive
from backend.core.agents.campaign_extract import extract_campaign_record
from backend.core.database.connection import get_database
from backend.core.database.repositories.resources import ResourceRepository
from backend.core.rag.parser import parse_file
from backend.core.rag.resource_import import refresh_resource_embedding
from backend.core.tasks import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60, time_limit=600)
def process_archive_task(
    self,
    archive_id: str,
    storage_path: str,
    filename: str,
    client_id: str,
    project_id: str,
    org_id: str = "",
):
    """Celery task: parse recap report → LLM extraction → distribute results."""
    try:
        asyncio.run(_process_archive(archive_id, storage_path, filename, client_id, project_id, org_id))
    except Exception as exc:
        logger.error(f"Archive processing failed for {archive_id}: {exc}")
        asyncio.run(_mark_status(archive_id, "failed", str(exc)))
        raise self.retry(exc=exc)


async def _process_archive(
    archive_id: str,
    storage_path: str,
    filename: str,
    client_id: str,
    project_id: str,
    org_id: str = "",
):
    db = await get_database()
    collection = db["project_archives"]

    await collection.update_one(
        {"_id": archive_id},
        {"$set": {"status": "processing"}},
    )

    file_bytes = Path(storage_path).read_bytes()
    report_text = parse_file(file_bytes, filename)

    if not report_text.strip():
        await collection.update_one(
            {"_id": archive_id},
            {"$set": {"status": "done", "extraction": None, "note": "Empty report"}},
        )
        return

    extraction = await extract_archive(report_text)
    extraction_dict = extraction.model_dump()

    # Campaign Knowledge Base: structured record extraction (Phase 5)
    campaign_record = await extract_campaign_record(report_text, source_archive_id=archive_id)
    campaign_dict = campaign_record.model_dump(by_alias=True)

    await collection.update_one(
        {"_id": archive_id},
        {"$set": {"status": "done", "extraction": extraction_dict}},
    )

    # Store campaign record for human review
    await _store_campaign_record(campaign_dict, client_id, project_id, archive_id, org_id)

    await _distribute_to_resources(extraction, client_id)


async def _store_campaign_record(
    campaign_dict: dict,
    client_id: str,
    project_id: str,
    archive_id: str,
    org_id: str = "",
):
    """Persist campaign record to MongoDB for human review."""
    db = await get_database()
    # Assign explicit string _id so API can query by string record_id.
    # model_dump(by_alias=True) sets _id=None; override with a real UUID.
    campaign_dict["_id"] = str(uuid.uuid4())
    campaign_dict["client_id"] = client_id
    campaign_dict["project_id"] = project_id
    campaign_dict["org_id"] = org_id
    campaign_dict["source_archive_id"] = archive_id
    await db["campaign_records"].insert_one(campaign_dict)
    logger.info(f"Campaign record stored for archive {archive_id}")



async def _distribute_to_resources(extraction, client_id: str):
    """Update resource collaboration_history and refresh embeddings from performance data."""
    if not extraction.resource_performances:
        return

    db = await get_database()
    repo = ResourceRepository(db)

    for perf in extraction.resource_performances:
        doc = await repo.find_by_name(client_id, perf.name)
        if not doc:
            continue

        collab_record = {
            "performance_summary": perf.performance_summary,
            "metrics": perf.metrics,
            "recommendation": perf.recommendation,
        }
        await repo.add_collaboration_record(doc["_id"], collab_record)
        updated_doc = await repo.get_by_id(doc["_id"])
        await refresh_resource_embedding(updated_doc, client_id)


async def _mark_status(archive_id: str, status: str, error: str = ""):
    db = await get_database()
    collection = db["project_archives"]
    update = {"status": status}
    if error:
        update["processing_error"] = error[:500]
    await collection.update_one({"_id": archive_id}, {"$set": update})
