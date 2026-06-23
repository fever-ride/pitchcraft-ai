"use client";

import { useEffect } from "react";
import { useDispatch } from "react-redux";
import {
  setCurrentNode,
  setPaused,
  addSlide,
  setNarrativeSuggestions,
  setCompleted,
  setError,
} from "@/store/pipelineSlice";
import { apiFetch } from "@/lib/api";

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

/**
 * Opens a WebSocket connection for the given pipeline and dispatches
 * Redux actions as events arrive.
 *
 * HITL responses are sent via HTTP (POST /api/v1/pipeline/{id}/confirm),
 * not through this WebSocket.
 */
export function usePipelineSocket(pipelineId: string | null) {
  const dispatch = useDispatch();

  useEffect(() => {
    if (!pipelineId) return;

    const ws = new WebSocket(`${WS_BASE}/ws/pipeline/${pipelineId}`);

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

    // On unexpected close, poll /status once so the backend auto-recover logic
    // can detect a stale 'running' state and restore it to 'paused' or 'error'.
    ws.onclose = (event) => {
      if (!event.wasClean) {
        apiFetch(`/api/v1/pipeline/${pipelineId}/status`)
          .then((res) => res.json())
          .then((data: { status: string; current_node?: string }) => {
            if (data.status === "paused" && data.current_node) {
              dispatch(setPaused(data.current_node));
            } else if (data.status === "error") {
              dispatch(setError("Pipeline stopped unexpectedly. Please rerun."));
            }
          })
          .catch(() => {/* status fetch failed — user already sees WS error */});
      }
    };

    return () => {
      ws.close();
    };
  }, [pipelineId, dispatch]);
}
