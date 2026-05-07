"use client";

import { useEffect, useRef, useCallback } from "react";
import { useDispatch } from "react-redux";
import {
  setCurrentNode,
  setPaused,
  addSlide,
  setNarrativeSuggestions,
  setCompleted,
  setError,
} from "@/store/pipelineSlice";

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export function usePipelineSocket(pipelineId: string | null) {
  const dispatch = useDispatch();
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!pipelineId) return;

    const ws = new WebSocket(`${WS_BASE}/ws/pipeline/${pipelineId}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      switch (data.event) {
        case "node_entered":
          dispatch(setCurrentNode(data.node));
          break;
        case "agent_started":
          dispatch(setCurrentNode(data.agent));
          break;
        case "agent_completed":
          break;
        case "hitl_required":
          dispatch(setPaused(data.node));
          break;
        case "slide_generated":
          dispatch(
            addSlide({
              index: data.slide_index,
              content: data.content,
              status: "pending",
            })
          );
          break;
        case "narrative_suggestions":
          dispatch(setNarrativeSuggestions(data.suggestions));
          break;
        case "pipeline_complete":
        case "pipeline_completed":
          dispatch(setCompleted(data.pptx_path || data.pptx_url));
          break;
        case "fallback_triggered":
        case "budget_warning":
          break;
      }
    };

    ws.onerror = () => {
      dispatch(setError("WebSocket connection error"));
    };

    return () => {
      ws.close();
    };
  }, [pipelineId, dispatch]);

  const sendEvent = useCallback((event: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(event));
    }
  }, []);

  return { sendEvent };
}
