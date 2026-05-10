"""File processing pipeline: parse → chunk → embed → index."""
import asyncio
import logging
from pathlib import Path

from backend.core.database.connection import get_database
from backend.core.database.repositories.files import FileRepository
from backend.core.rag.chunker import semantic_chunk, semantic_chunk_with_metadata
from backend.core.rag.embedder import embed_texts
from backend.core.rag.indexer import resolve_namespace, upsert_vectors
from backend.core.rag.parser import parse_file, parse_file_structured
from backend.core.tasks import celery_app

logger = logging.getLogger(__name__)


def _build_contextual_prefix(
    client_name: str | None,
    file_type: str,
    filename: str,
    page_number: int | None = None,
    slide_index: int | None = None,
) -> str:
    """Build metadata prefix for contextual embedding.

    Format: [ClientName | file_type | filename | location]
    """
    parts = []
    if client_name:
        parts.append(client_name)
    parts.append(file_type)
    parts.append(Path(filename).stem)

    if slide_index is not None:
        parts.append(f"slide {slide_index}")
    elif page_number is not None:
        parts.append(f"page {page_number}")

    return "[" + " | ".join(parts) + "]\n"


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def process_file_task(self, file_id: str, storage_path: str, filename: str, file_type: str, client_id: str, project_id: str | None, client_name: str | None = None):
    """Celery task: read from disk, parse, chunk, embed, and index a file."""
    try:
        asyncio.run(_process_file(file_id, storage_path, filename, file_type, client_id, project_id, client_name))
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
    client_name: str | None = None,
):
    file_bytes = Path(storage_path).read_bytes()
    db = await get_database()
    repo = FileRepository(db)

    await repo.update(file_id, {"processing_status": "processing"})

    parsed = parse_file_structured(file_bytes, filename)
    if not parsed.segments:
        await repo.update(file_id, {
            "processing_status": "done",
            "chunk_count": 0,
        })
        return

    chunk_metas = semantic_chunk_with_metadata(parsed.segments, file_type=file_type)
    if not chunk_metas:
        await repo.update(file_id, {
            "processing_status": "done",
            "chunk_count": 0,
        })
        return

    embedding_texts = []
    extra_metadata = []

    for cm in chunk_metas:
        prefix = _build_contextual_prefix(
            client_name=client_name,
            file_type=file_type,
            filename=filename,
            page_number=cm.page_number,
            slide_index=cm.slide_index,
        )
        embedding_texts.append(prefix + cm.text)

        meta: dict = {"filename": filename, "file_type": file_type}
        if cm.page_number is not None:
            meta["page_number"] = cm.page_number
        if cm.slide_index is not None:
            meta["slide_index"] = cm.slide_index
        extra_metadata.append(meta)

    embeddings = await embed_texts(embedding_texts)

    raw_chunks = [cm.text for cm in chunk_metas]

    namespace = resolve_namespace(file_type, client_id, project_id)
    chunk_count = upsert_vectors(namespace, file_id, raw_chunks, embeddings, extra_metadata=extra_metadata)

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
