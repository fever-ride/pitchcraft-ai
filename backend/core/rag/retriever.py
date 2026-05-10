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
    def __init__(
        self,
        text: str,
        score: float,
        file_id: str,
        chunk_index: int,
        page_number: int | None = None,
        slide_index: int | None = None,
        filename: str | None = None,
    ):
        self.text = text
        self.score = score
        self.file_id = file_id
        self.chunk_index = chunk_index
        self.page_number = page_number
        self.slide_index = slide_index
        self.filename = filename

    @property
    def source_location(self) -> str | None:
        """Human-readable source location for citations."""
        if self.slide_index is not None:
            prefix = f"{self.filename}, " if self.filename else ""
            return f"{prefix}slide {self.slide_index}"
        if self.page_number is not None:
            prefix = f"{self.filename}, " if self.filename else ""
            return f"{prefix}page {self.page_number}"
        return self.filename

    def to_dict(self) -> dict:
        d = {
            "text": self.text,
            "score": self.score,
            "file_id": self.file_id,
            "chunk_index": self.chunk_index,
        }
        if self.page_number is not None:
            d["page_number"] = self.page_number
        if self.slide_index is not None:
            d["slide_index"] = self.slide_index
        if self.filename:
            d["filename"] = self.filename
        if self.source_location:
            d["source_location"] = self.source_location
        return d


async def retrieve(
    query: str,
    namespaces: list[str],
    top_k: int = 5,
    score_threshold: float = 0.5,
    metadata_filter: dict | None = None,
) -> list[RAGResult]:
    """Retrieve relevant chunks from one or more Pinecone namespaces.

    metadata_filter: optional Pinecone filter dict, e.g.
      {"platform": {"$in": ["douyin"]}, "followers_count": {"$gte": 500000}}
    """
    query_embedding = await embed_query(query)
    index = _get_index()

    results: list[RAGResult] = []

    for ns in namespaces:
        query_params = {
            "vector": query_embedding,
            "namespace": ns,
            "top_k": top_k,
            "include_metadata": True,
        }
        if metadata_filter:
            query_params["filter"] = metadata_filter

        resp = index.query(**query_params)
        for match in resp.matches:
            if match.score >= score_threshold:
                results.append(RAGResult(
                    text=match.metadata.get("text", ""),
                    score=match.score,
                    file_id=match.metadata.get("file_id", ""),
                    chunk_index=match.metadata.get("chunk_index", 0),
                    page_number=match.metadata.get("page_number"),
                    slide_index=match.metadata.get("slide_index"),
                    filename=match.metadata.get("filename"),
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
        f"brand_style_{client_id}",
    ]
    if project_id:
        namespaces.append(f"project_{project_id}")

    return await retrieve(query, namespaces, top_k=top_k)
