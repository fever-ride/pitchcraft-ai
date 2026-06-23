"""WebSocket manager for pipeline progress broadcasting.

Clients connect to /ws/pipeline/{pipeline_id} to receive real-time events:
  - node_entered       — a pipeline node has started executing
  - hitl_required      — pipeline is paused at a HITL checkpoint (with interrupt data)
  - slide_generated    — a slide was generated (slide_index + content)
  - pipeline_complete  — pipeline finished (pptx_path)

HITL responses are NOT sent through WebSocket in Option B.
Use POST /api/v1/pipeline/{id}/confirm to submit a HITL response.

Clients also connect to /ws/campaigns/{org_id} to receive:
  - campaign_record_ready — a new campaign record is ready for review
"""
import asyncio

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.core.config import settings

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, pipeline_id: str, websocket: WebSocket):
        await websocket.accept()
        if pipeline_id not in self.active_connections:
            self.active_connections[pipeline_id] = []
        self.active_connections[pipeline_id].append(websocket)

    def disconnect(self, pipeline_id: str, websocket: WebSocket):
        if pipeline_id in self.active_connections:
            self.active_connections[pipeline_id].remove(websocket)
            if not self.active_connections[pipeline_id]:
                del self.active_connections[pipeline_id]

    async def send_event(self, pipeline_id: str, event: dict):
        if pipeline_id in self.active_connections:
            for connection in self.active_connections[pipeline_id]:
                await connection.send_json(event)

    async def broadcast_slide_generated(self, pipeline_id: str, slide_index: int, content: dict):
        await self.send_event(pipeline_id, {
            "event": "slide_generated",
            "slide_index": slide_index,
            "content": content,
        })

    async def broadcast_node_entered(self, pipeline_id: str, node: str):
        await self.send_event(pipeline_id, {
            "event": "node_entered",
            "node": node,
        })

    async def broadcast_hitl_required(self, pipeline_id: str, node: str, data: dict):
        await self.send_event(pipeline_id, {
            "event": "hitl_required",
            "node": node,
            "data": data,
        })

    async def broadcast_pipeline_complete(self, pipeline_id: str, pptx_path: str):
        await self.send_event(pipeline_id, {
            "event": "pipeline_complete",
            "pptx_path": pptx_path,
        })

    async def broadcast_narrative_suggestions(self, pipeline_id: str, suggestions: list):
        await self.send_event(pipeline_id, {
            "event": "narrative_suggestions",
            "suggestions": suggestions,
        })


manager = ConnectionManager()


@router.websocket("/ws/campaigns/{org_id}")
async def campaigns_websocket(websocket: WebSocket, org_id: str):
    """Push-only WebSocket for campaign extraction completion events.

    Subscribes to Redis pub/sub channel campaign:{org_id} and forwards
    campaign_record_ready events to the connected frontend client.
    """
    await websocket.accept()
    r = aioredis.from_url(settings.redis_url)
    pubsub = r.pubsub()
    await pubsub.subscribe(f"campaign:{org_id}")
    try:
        async def _listen():
            async for message in pubsub.listen():
                if message["type"] == "message":
                    await websocket.send_text(message["data"].decode())

        listen_task = asyncio.create_task(_listen())
        # Keep alive; ignore any client messages
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            listen_task.cancel()
    finally:
        await pubsub.unsubscribe(f"campaign:{org_id}")
        await r.aclose()


@router.websocket("/ws/pipeline/{pipeline_id}")
async def pipeline_websocket(websocket: WebSocket, pipeline_id: str):
    """Receive-only WebSocket for pipeline progress events.

    Clients should only LISTEN here. HITL responses must be sent via
    POST /api/v1/pipeline/{pipeline_id}/confirm (HTTP).
    """
    await manager.connect(pipeline_id, websocket)
    try:
        # Keep connection alive; ignore any incoming messages
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(pipeline_id, websocket)
