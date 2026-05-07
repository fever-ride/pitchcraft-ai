from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.v1.endpoints import (
    analytics,
    auth,
    clients,
    files,
    pipeline,
    projects,
    proposals,
    resources,
    users,
)
from backend.api.v1.websocket import router as ws_router
from backend.core.config import settings

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(clients.router, prefix="/api/v1/clients", tags=["clients"])
app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
app.include_router(files.router, prefix="/api/v1/files", tags=["files"])
app.include_router(pipeline.router, prefix="/api/v1/pipeline", tags=["pipeline"])
app.include_router(proposals.router, prefix="/api/v1/proposals", tags=["proposals"])
app.include_router(resources.router, prefix="/api/v1/resources", tags=["resources"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["analytics"])
app.include_router(ws_router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
