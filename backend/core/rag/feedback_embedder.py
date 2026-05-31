"""Embed approved feedback directions into brand namespace for future retrieval."""
from backend.core.database.connection import get_database
from backend.core.database.repositories.brand_profiles import BrandProfileRepository
from backend.core.database.repositories.feedback import FeedbackRepository
from backend.core.rag.embedder import embed_texts
from backend.core.rag.indexer import upsert_vectors


async def embed_feedback_directions(client_id: str, feedback_id: str, directions: list[str]):
    """Embed approved directions into brand_spec namespace so strategy agent can retrieve them.

    Also mirrors approved_directions into the structured BrandProfile (MongoDB) so
    they are directly available in agent prompts without requiring a retrieval step.
    """
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
    feedback_repo = FeedbackRepository(db)
    await feedback_repo.mark_embedded(feedback_id)

    # Mirror approved directions into the structured BrandProfile so they surface
    # in agent prompts (phase1 context + brand_check) without an extra retrieval call.
    brand_profile_repo = BrandProfileRepository(db)
    await brand_profile_repo.add_feedback_directions(client_id, approved=directions)


async def process_unembedded_feedback():
    """Batch job: find and embed all unprocessed approved directions.

    Also syncs rejected_directions to BrandProfile for records that pre-date
    the sync logic (no-op for records already processed via the POST endpoint).
    """
    db = await get_database()
    repo = FeedbackRepository(db)
    unembedded = await repo.find_unembedded()

    brand_profile_repo = BrandProfileRepository(db)

    for doc in unembedded:
        client_id = doc["client_id"]
        await embed_feedback_directions(
            client_id=client_id,
            feedback_id=str(doc["_id"]),
            directions=doc.get("approved_directions", []),
        )
        # Sync any rejected directions that weren't captured by the POST endpoint
        rejected = doc.get("rejected_directions", [])
        if rejected:
            await brand_profile_repo.add_feedback_directions(client_id, rejected=rejected)
