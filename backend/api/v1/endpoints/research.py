from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from backend.api.v1.permissions import CurrentUser, get_current_user

router = APIRouter()

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB per image
MAX_IMAGES = 10


class VisualAnalysisResponse(BaseModel):
    results: list[dict]
    count: int


@router.post("/competitor-screenshots", response_model=VisualAnalysisResponse)
async def analyze_competitor_screenshots(
    files: list[UploadFile] = File(...),
    user: CurrentUser = Depends(get_current_user),
):
    """Upload competitor screenshots for visual analysis. Returns structured insights per image."""
    from backend.core.agents.visual_analysis import analyze_competitor_batch

    if len(files) > MAX_IMAGES:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_IMAGES} images per request")

    images = []
    for f in files:
        content = await f.read()
        if len(content) > MAX_IMAGE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"Image '{f.filename}' exceeds 5 MB limit",
            )
        mime = f.content_type or "image/png"
        images.append((content, mime))

    if not images:
        return VisualAnalysisResponse(results=[], count=0)

    results = await analyze_competitor_batch(images, lang="zh")
    return VisualAnalysisResponse(results=results, count=len(results))
