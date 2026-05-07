from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

app = FastAPI(title="BGE-M3 Embedding Service")

model = None


@app.on_event("startup")
async def load_model():
    global model
    model = SentenceTransformer("BAAI/bge-m3")


class EmbedRequest(BaseModel):
    texts: list[str]


class EmbedResponse(BaseModel):
    embeddings: list[list[float]]


@app.post("/embed", response_model=EmbedResponse)
async def embed(request: EmbedRequest):
    embeddings = model.encode(request.texts, normalize_embeddings=True)
    return EmbedResponse(embeddings=embeddings.tolist())


@app.get("/health")
async def health():
    return {"status": "ok", "model": "BAAI/bge-m3"}
