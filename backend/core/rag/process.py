"""File processing pipeline: parse → chunk → embed → index."""
import asyncio
import logging
from pathlib import Path

from backend.core.database.connection import get_database
from backend.core.database.repositories.files import FileRepository
from backend.core.rag.chunker import semantic_chunk
from backend.core.rag.embedder import embed_texts
from backend.core.rag.indexer import resolve_namespace, upsert_vectors
from backend.core.rag.parser import parse_file
from backend.core.tasks import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def process_file_task(self, file_id: str, storage_path: str, filename: str, file_type: str, client_id: str, project_id: str | None):
    """Celery task: read from disk, parse, chunk, embed, and index a file."""
    try:
        asyncio.run(_process_file(file_id, storage_path, filename, file_type, client_id, project_id))
    except Exception as exc:
        logger.error(f"File processing failed for {file_id}: {exc}")
        asyncio.run(_mark_failed(file_id, str(exc)))
        raise self.retry(exc=exc)


async def _process_file(
    file_id: str,
    storage_path: str,
    filename: str,
    file_type: str,
    client_id: str,
    project_id: str | None,
):
    file_bytes = Path(storage_path).read_bytes()
    db = await get_database()
    repo = FileRepository(db)

    await repo.update(file_id, {"processing_status": "processing"})

    text = parse_file(file_bytes, filename)
    if not text.strip():
        await repo.update(file_id, {
            "processing_status": "done",
            "chunk_count": 0,
        })
        return

    chunks = semantic_chunk(text)
    embeddings = await embed_texts(chunks)

    namespace = resolve_namespace(file_type, client_id, project_id)
    chunk_count = upsert_vectors(namespace, file_id, chunks, embeddings)

    await repo.update(file_id, {
        "processing_status": "done",
        "pinecone_namespace": namespace,
        "chunk_count": chunk_count,
    })


async def _mark_failed(file_id: str, error: str):
    db = await get_database()
    repo = FileRepository(db)
    await repo.update(file_id, {
        "processing_status": "failed",
        "processing_error": error[:500],
    })
