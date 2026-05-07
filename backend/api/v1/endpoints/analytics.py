from fastapi import APIRouter, Depends

from backend.api.v1.permissions import CurrentUser, get_current_user

router = APIRouter()


@router.get("/pipeline-metrics")
async def get_pipeline_metrics(user: CurrentUser = Depends(get_current_user)):
    # TODO: aggregate stage_metrics data
    return {}


@router.get("/cache-stats")
async def get_cache_stats(user: CurrentUser = Depends(get_current_user)):
    # TODO: return cache hit rate from Redis
    return {}
