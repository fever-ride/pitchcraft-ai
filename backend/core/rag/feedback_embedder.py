"""Embed approved feedback directions into brand namespace for future retrieval."""
from backend.core.database.connection import get_database
from backend.core.database.repositories.feedback import FeedbackRepository
from backend.core.rag.embedder import embed_texts
from backend.core.rag.indexer import upsert_vectors


async def embed_feedback_directions(client_id: str, feedback_id: str, directions: list[str]):
    """Embed approved directions into brand_spec namespace so strategy agent can retrieve them."""
    if not directions:
        return

    texts = [f"[Approved direction] {d}" for d in directions]
    embeddings = await embed_texts(texts)

    namespace = f"brand_spec_{client_id}"
    upsert_vectors(
        namespace=namespace,
        file_id=f"feedback_{feedback_id}",
        chunks=texts,
        embeddings=embeddings,
    )

    db = await get_database()
    repo = FeedbackRepository(db)
    await repo.mark_embedded(feedback_id)


async def process_unembedded_feedback():
    """Batch job: find and embed all unprocessed approved directions."""
    db = await get_database()
    repo = FeedbackRepository(db)
    unembedded = await repo.find_unembedded()

    for doc in unembedded:
        await embed_feedback_directions(
            client_id=doc["client_id"],
            feedback_id=str(doc["_id"]),
            directions=doc.get("approved_directions", []),
        )
