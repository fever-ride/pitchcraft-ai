import asyncio
import logging

from celery import Celery

from backend.core.config import settings

logger = logging.getLogger(__name__)


def run_async(coro):
    """Run an async coroutine in a fresh event loop.

    Always creates a new loop instead of relying on asyncio.run(), which fails
    in Celery forked workers after the first task closes the previous loop.
    Every Celery task that wraps async code should use this helper.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        try:
            loop.close()
        except Exception:
            pass
        asyncio.set_event_loop(None)

celery_app = Celery(
    "pitchcraft",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    include=[
        "backend.core.rag.archive_process",
        "backend.core.rag.resource_import",
    ],
)
