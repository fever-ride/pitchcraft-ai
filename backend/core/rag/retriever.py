from pinecone import Pinecone

from backend.core.config import settings
from backend.core.rag.embedder import embed_query

_pc: Pinecone | None = None


def _get_index():
    global _pc
    if _pc is None:
        _pc = Pinecone(api_key=settings.pinecone_api_key)
    return _pc.Index(settings.pinecone_index_name)


class RAGResult:
    def __init__(self, text: str, score: float, file_id: str, chunk_index: int):
        self.text = text
        self.score = score
        self.file_id = file_id
        self.chunk_index = chunk_index

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "score": self.score,
            "file_id": self.file_id,
            "chunk_index": self.chunk_index,
        }


async def retrieve(
    query: str,
    namespaces: list[str],
    top_k: int = 5,
    score_threshold: float = 0.5,
) -> list[RAGResult]:
    """Retrieve relevant chunks from one or more Pinecone namespaces."""
    query_embedding = await embed_query(query)
    index = _get_index()

    results: list[RAGResult] = []

    for ns in namespaces:
        resp = index.query(
            vector=query_embedding,
            namespace=ns,
            top_k=top_k,
            include_metadata=True,
        )
        for match in resp.matches:
            if match.score >= score_threshold:
                results.append(RAGResult(
                    text=match.metadata.get("text", ""),
                    score=match.score,
                    file_id=match.metadata.get("file_id", ""),
                    chunk_index=match.metadata.get("chunk_index", 0),
                ))

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:top_k]


async def retrieve_for_client(
    query: str,
    client_id: str,
    project_id: str | None = None,
    top_k: int = 5,
) -> list[RAGResult]:
    """Convenience method: searches Brand Library + Project Library namespaces."""
    namespaces = [
        f"brand_spec_{client_id}",
        f"brand_history_{client_id}",
    ]
    if project_id:
        namespaces.append(f"project_{project_id}")

    return await retrieve(query, namespaces, top_k=top_k)
