import httpx

from backend.core.config import settings

BATCH_SIZE = 32


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Call the BGE-M3 embedding service. Batches large inputs automatically."""
    all_embeddings: list[list[float]] = []

    async with httpx.AsyncClient(timeout=60.0) as client:
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i : i + BATCH_SIZE]
            resp = await client.post(
                f"{settings.embedding_service_url}/embed",
                json={"texts": batch},
            )
            resp.raise_for_status()
            all_embeddings.extend(resp.json()["embeddings"])

    return all_embeddings


async def embed_query(text: str) -> list[float]:
    """Embed a single query text."""
    results = await embed_texts([text])
    return results[0]
