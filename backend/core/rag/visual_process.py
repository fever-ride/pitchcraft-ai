"""Visual file processing pipeline: render → analyze → embed → index."""
import json
import logging
import tempfile
from pathlib import Path

from backend.core.database.connection import get_database
from backend.core.database.repositories.files import FileRepository
from backend.core.rag.embedder import embed_texts
from backend.core.rag.indexer import upsert_vectors
from backend.core.rag.visual_renderer import generate_thumbnail, render_to_pngs
from backend.core.rag.visual_style import (
    extract_batch_styles,
    generate_visual_summary,
    style_to_embedding_text,
    summary_to_embedding_text,
)
from backend.core.tasks import celery_app, run_async

logger = logging.getLogger(__name__)

THUMBNAIL_DIR = Path("/data/thumbnails")


@celery_app.task(bind=True, max_retries=1, default_retry_delay=60, time_limit=600)
def process_visual_file_task(
    self,
    file_id: str,
    storage_path: str,
    filename: str,
    client_id: str,
):
    """Celery task: render visual file, extract styles, embed, and index."""
    try:
        run_async(_process_visual_file(file_id, storage_path, filename, client_id))
    except Exception as exc:
        logger.error(f"Visual processing failed for {file_id}: {exc}")
        try:
            run_async(_mark_failed(file_id, str(exc)))
        except Exception as mark_exc:
            logger.error(f"Failed to mark file {file_id} as failed: {mark_exc}")
        raise self.retry(exc=exc)


async def _process_visual_file(
    file_id: str,
    storage_path: str,
    filename: str,
    client_id: str,
):
    file_bytes = Path(storage_path).read_bytes()
    db = await get_database()
    repo = FileRepository(db)

    await repo.update(file_id, {"processing_status": "processing"})

    # 1. Render to PNGs
    with tempfile.TemporaryDirectory() as render_dir:
        png_paths = await render_to_pngs(file_bytes, filename, render_dir)

        if not png_paths:
            await repo.update(file_id, {
                "processing_status": "done",
                "chunk_count": 0,
                "processing_error": "No pages rendered (LibreOffice/pdftoppm may not be available)",
            })
            return

        # 2. Save thumbnails
        thumbnail_dir = THUMBNAIL_DIR / client_id / file_id
        thumbnail_dir.mkdir(parents=True, exist_ok=True)
        thumbnail_paths = []
        for png_path in png_paths:
            thumb_bytes = generate_thumbnail(png_path)
            thumb_name = Path(png_path).name
            thumb_path = thumbnail_dir / thumb_name
            thumb_path.write_bytes(thumb_bytes)
            thumbnail_paths.append(str(thumb_path))

        # 3. Extract styles via Claude Vision (skip mostly-text slides)
        slide_styles = await extract_batch_styles(png_paths, batch_size=5)

        if not slide_styles:
            await repo.update(file_id, {
                "processing_status": "done",
                "chunk_count": 0,
                "metadata": {"thumbnails": thumbnail_paths, "note": "All slides are text-heavy"},
            })
            return

        # 4. Generate file-level summary
        summary = await generate_visual_summary(slide_styles)

        # 5. Build embedding texts
        texts = [style_to_embedding_text(s) for s in slide_styles]
        summary_text = summary_to_embedding_text(summary)
        texts.append(summary_text)

        # 6. Embed and index
        embeddings = await embed_texts(texts)
        namespace = f"brand_spec_{client_id}"
        chunk_count = upsert_vectors(namespace, file_id, texts, embeddings)

        # 7. Update file record
        await repo.update(file_id, {
            "processing_status": "done",
            "pinecone_namespace": namespace,
            "chunk_count": chunk_count,
            "metadata": {
                "thumbnails": thumbnail_paths,
                "slide_count": len(png_paths),
                "visual_slides_analyzed": len(slide_styles),
                "visual_summary": summary,
            },
        })

        logger.info(
            f"Visual processing done for {file_id}: "
            f"{len(png_paths)} pages, {len(slide_styles)} visual slides, "
            f"{chunk_count} chunks indexed"
        )


async def _mark_failed(file_id: str, error: str):
    db = await get_database()
    repo = FileRepository(db)
    await repo.update(file_id, {
        "processing_status": "failed",
        "processing_error": error[:500],
    })
