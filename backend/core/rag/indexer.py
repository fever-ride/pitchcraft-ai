from pinecone import Pinecone

from backend.core.config import settings
from backend.core.models.file import FileType

UPSERT_BATCH = 100

_pc: Pinecone | None = None


def _get_index():
    global _pc
    if _pc is None:
        _pc = Pinecone(api_key=settings.pinecone_api_key)
    return _pc.Index(settings.pinecone_index_name)


def resolve_namespace(file_type: str, client_id: str, project_id: str | None) -> str:
    if file_type in (FileType.BRAND_SPEC, FileType.BRAND_HISTORY_PROPOSAL, FileType.BRAND_HISTORY_COPY):
        prefix = "brand_spec" if file_type == FileType.BRAND_SPEC else "brand_history"
        return f"{prefix}_{client_id}"
    return f"project_{project_id or client_id}"


def upsert_vectors(
    namespace: str,
    file_id: str,
    chunks: list[str],
    embeddings: list[list[float]],
    extra_metadata: list[dict] | None = None,
):
    index = _get_index()
    vectors = []
    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        meta = {
            "file_id": file_id,
            "chunk_index": i,
            "text": chunk[:1000],
        }
        if extra_metadata and i < len(extra_metadata):
            meta.update(extra_metadata[i])
        vectors.append({
            "id": f"{file_id}_{i}",
            "values": emb,
            "metadata": meta,
        })

    for i in range(0, len(vectors), UPSERT_BATCH):
        batch = vectors[i : i + UPSERT_BATCH]
        index.upsert(vectors=batch, namespace=namespace)

    return len(vectors)


def delete_by_file(namespace: str, file_id: str):
    index = _get_index()
    index.delete(
        filter={"file_id": {"$eq": file_id}},
        namespace=namespace,
    )
