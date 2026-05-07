from fastapi import APIRouter, WebSocket, WebSocketDisconnect

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


@router.websocket("/ws/pipeline/{pipeline_id}")
async def pipeline_websocket(websocket: WebSocket, pipeline_id: str):
    await manager.connect(pipeline_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            event_type = data.get("event")

            if event_type == "hitl_response":
                from backend.core.graph.executor import PipelineExecutor

                executor = PipelineExecutor(pipeline_id)
                await executor.resume({
                    "action": data.get("action", "confirm"),
                    "feedback": data.get("feedback"),
                    "refresh_research": data.get("refresh_research", False),
                    "edits": data.get("edits"),
                    "flagged_indices": data.get("flagged_indices"),
                })

            elif event_type == "research_refresh":
                from backend.core.graph.executor import PipelineExecutor

                executor = PipelineExecutor(pipeline_id)
                await executor.resume({
                    "action": "revise",
                    "refresh_research": True,
                })

    except WebSocketDisconnect:
        manager.disconnect(pipeline_id, websocket)
