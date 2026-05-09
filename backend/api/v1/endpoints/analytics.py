from fastapi import APIRouter, Depends

import redis.asyncio as aioredis

from backend.api.v1.permissions import CurrentUser, get_current_user
from backend.core.config import settings
from backend.core.database.connection import get_database

router = APIRouter()


@router.get("/pipeline-metrics")
async def get_pipeline_metrics(user: CurrentUser = Depends(get_current_user)):
    db = await get_database()
    collection = db["stage_metrics"]

    pipeline_count = await collection.count_documents({})
    if pipeline_count == 0:
        return {"pipeline_count": 0}

    # Average execution time
    avg_cursor = collection.aggregate([
        {"$match": {"request_budget.total_seconds": {"$exists": True}}},
        {"$group": {
            "_id": None,
            "avg_duration_s": {"$avg": "$request_budget.total_seconds"},
            "avg_llm_calls": {"$avg": "$request_budget.llm_calls_used"},
            "avg_search_calls": {"$avg": "$request_budget.search_calls_used"},
            "max_duration_s": {"$max": "$request_budget.total_seconds"},
            "count": {"$sum": 1},
        }},
    ])
    avg_data = {}
    async for doc in avg_cursor:
        avg_data = doc
        break

    # Per-stage average duration
    stage_names = [
        "brief_analyzer", "research_agent", "strategy_phase2",
        "resource_agent", "deck_orchestrator", "slide_content",
        "narrative_agent", "ppt_builder",
    ]
    stage_durations = {}
    for stage in stage_names:
        cursor = collection.aggregate([
            {"$match": {f"{stage}.duration_s": {"$exists": True}}},
            {"$group": {
                "_id": None,
                "avg": {"$avg": f"${stage}.duration_s"},
                "count": {"$sum": 1},
            }},
        ])
        async for doc in cursor:
            stage_durations[stage] = {
                "avg_duration_s": round(doc["avg"], 1),
                "trigger_count": doc["count"],
            }
            break

    # Resource agent trigger rate (how often it actually runs vs total pipelines)
    resource_trigger_count = stage_durations.get("resource_agent", {}).get("trigger_count", 0)

    return {
        "pipeline_count": pipeline_count,
        "avg_duration_s": round(avg_data.get("avg_duration_s", 0), 1),
        "max_duration_s": round(avg_data.get("max_duration_s", 0), 1),
        "avg_llm_calls": round(avg_data.get("avg_llm_calls", 0), 1),
        "avg_search_calls": round(avg_data.get("avg_search_calls", 0), 1),
        "resource_agent_trigger_rate": round(resource_trigger_count / max(pipeline_count, 1) * 100, 1),
        "stage_durations": stage_durations,
    }


@router.get("/cache-stats")
async def get_cache_stats(user: CurrentUser = Depends(get_current_user)):
    r = aioredis.from_url(settings.redis_url)
    try:
        keys = []
        async for key in r.scan_iter(match="research:*"):
            keys.append(key)
            if len(keys) >= 1000:
                break
        return {
            "cached_research_entries": len(keys),
            "ttl_days": 30,
        }
    finally:
        await r.aclose()


@router.get("/feedback-stats")
async def get_feedback_stats(user: CurrentUser = Depends(get_current_user)):
    db = await get_database()
    feedback_col = db["feedback"]

    total = await feedback_col.count_documents({})
    if total == 0:
        return {"total_feedback": 0}

    rerun_triggered = await feedback_col.count_documents({"rerun_triggered": True})
    with_approved = await feedback_col.count_documents({"approved_directions": {"$ne": []}})
    with_rejected = await feedback_col.count_documents({"rejected_directions": {"$ne": []}})

    # Target distribution
    target_cursor = feedback_col.aggregate([
        {"$group": {"_id": "$target", "count": {"$sum": 1}}},
    ])
    target_dist = {}
    async for doc in target_cursor:
        target_dist[doc["_id"] or "overall"] = doc["count"]

    return {
        "total_feedback": total,
        "rerun_triggered_count": rerun_triggered,
        "rerun_trigger_rate": round(rerun_triggered / total * 100, 1),
        "with_approved_directions": with_approved,
        "with_rejected_directions": with_rejected,
        "target_distribution": target_dist,
    }


@router.get("/brief-stats")
async def get_brief_stats(user: CurrentUser = Depends(get_current_user)):
    db = await get_database()
    versions_col = db["proposal_versions"]

    total = await versions_col.count_documents({})
    if total == 0:
        return {"total_versions": 0}

    # Trigger distribution (pipeline_complete vs rerun vs rollback)
    trigger_cursor = versions_col.aggregate([
        {"$group": {"_id": "$trigger", "count": {"$sum": 1}}},
    ])
    trigger_dist = {}
    async for doc in trigger_cursor:
        trigger_dist[doc["_id"] or "unknown"] = doc["count"]

    return {
        "total_versions": total,
        "trigger_distribution": trigger_dist,
        "rerun_count": sum(v for k, v in trigger_dist.items() if k == "rerun"),
        "rollback_count": sum(v for k, v in trigger_dist.items() if "rollback" in k),
    }
