"""Project archive processing: parse report → extract → distribute to multiple stores."""
import asyncio
import logging
from pathlib import Path

from backend.core.agents.archive import extract_archive
from backend.core.database.connection import get_database
from backend.core.rag.chunker import semantic_chunk
from backend.core.rag.embedder import embed_texts
from backend.core.rag.indexer import upsert_vectors
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
):
    """Celery task: parse recap report → LLM extraction → distribute results."""
    try:
        asyncio.run(_process_archive(archive_id, storage_path, filename, client_id, project_id))
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

    await collection.update_one(
        {"_id": archive_id},
        {"$set": {"status": "done", "extraction": extraction_dict}},
    )

    await _distribute_to_brand_history(report_text, extraction, client_id, archive_id)
    await _distribute_to_resources(extraction, client_id)


async def _distribute_to_brand_history(
    report_text: str,
    extraction,
    client_id: str,
    archive_id: str,
):
    """Store strategy learnings + audience insights in brand_history namespace."""
    texts_to_embed = []

    if extraction.project_summary:
        texts_to_embed.append(f"Project Summary: {extraction.project_summary}")

    for learning in extraction.strategy_learnings:
        texts_to_embed.append(f"Strategy Learning: {learning}")

    for insight in extraction.audience_insights:
        texts_to_embed.append(f"Audience Insight: {insight}")

    for content_insight in extraction.content_insights:
        texts_to_embed.append(f"Content Insight: {content_insight}")

    if not texts_to_embed:
        chunks = semantic_chunk(report_text)
        if not chunks:
            return
        texts_to_embed = chunks

    embeddings = await embed_texts(texts_to_embed)
    namespace = f"brand_history_{client_id}"
    upsert_vectors(namespace, archive_id, texts_to_embed, embeddings)


async def _distribute_to_resources(extraction, client_id: str):
    """Update resource collaboration_history and refresh embeddings from performance data."""
    if not extraction.resource_performances:
        return

    db = await get_database()
    collection = db["resources"]

    for perf in extraction.resource_performances:
        doc = await collection.find_one({
            "client_id": client_id,
            "name": {"$regex": f"^{perf.name}$", "$options": "i"},
        })
        if not doc:
            continue

        collab_record = {
            "performance_summary": perf.performance_summary,
            "metrics": perf.metrics,
            "recommendation": perf.recommendation,
        }
        await collection.update_one(
            {"_id": doc["_id"]},
            {"$push": {"collaboration_history": collab_record}},
        )

        updated_doc = await collection.find_one({"_id": doc["_id"]})
        await refresh_resource_embedding(updated_doc, client_id)


async def _mark_status(archive_id: str, status: str, error: str = ""):
    db = await get_database()
    collection = db["project_archives"]
    update = {"status": status}
    if error:
        update["processing_error"] = error[:500]
    await collection.update_one({"_id": archive_id}, {"$set": update})
