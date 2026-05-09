from fastapi import APIRouter, Depends, File, UploadFile, status
from pydantic import BaseModel

from backend.api.v1.permissions import CurrentUser, get_current_user

router = APIRouter()


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
    from backend.core.language.detector import detect_language

    images = []
    for f in files[:10]:  # Max 10 screenshots per request
        content = await f.read()
        mime = f.content_type or "image/png"
        images.append((content, mime))

    if not images:
        return VisualAnalysisResponse(results=[], count=0)

    results = await analyze_competitor_batch(images, lang="zh")
    return VisualAnalysisResponse(results=results, count=len(results))
