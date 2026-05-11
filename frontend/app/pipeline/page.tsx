"use client";

import { useState } from "react";
import { useSelector, useDispatch } from "react-redux";
import { RootState } from "@/store/store";
import { setPipelineId, reset } from "@/store/pipelineSlice";
import { usePipelineSocket } from "@/hooks/usePipelineSocket";
import { api } from "@/lib/api";
import { BriefInput } from "@/components/pipeline/BriefInput";
import { HitlBrief } from "@/components/pipeline/HitlBrief";
import { HitlStrategy } from "@/components/pipeline/HitlStrategy";
import { HitlStructure } from "@/components/pipeline/HitlStructure";
import { HitlMedia } from "@/components/pipeline/HitlMedia";
import { GalleryView } from "@/components/gallery/GalleryView";
import { PipelineProgress } from "@/components/pipeline/PipelineProgress";

export default function PipelinePage() {
  const dispatch = useDispatch();
  const { pipelineId, status, currentNode } = useSelector(
    (state: RootState) => state.pipeline
  );
  const { sendEvent } = usePipelineSocket(pipelineId);
  const [error, setError] = useState<string | null>(null);

  const handleStart = async (brief: string, clientId: string, projectId: string, outputLanguage: string) => {
    try {
      setError(null);
      const result = await api.startPipeline({
        raw_brief: brief,
        client_id: clientId,
        project_id: projectId,
        output_language: outputLanguage,
      });
      dispatch(setPipelineId(result.pipeline_id));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to start pipeline");
    }
  };

  const handleConfirm = (node: string, edits?: Record<string, unknown>) => {
    sendEvent({ event: "hitl_response", node, action: "confirm", edits });
  };

  const handleRevise = (node: string, feedback: string) => {
    sendEvent({ event: "hitl_response", node, action: "revise", feedback });
  };

  if (!pipelineId) {
    return (
      <div className="max-w-3xl mx-auto p-8">
        <h1 className="text-2xl font-bold mb-6">New Proposal</h1>
        <BriefInput onSubmit={handleStart} />
        {error && <p className="mt-4 text-red-600 text-sm">{error}</p>}
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col">
      <PipelineProgress currentNode={currentNode} status={status} />

      <div className="flex-1 overflow-hidden">
        {currentNode === "hitl_brief" && (
          <HitlBrief
            pipelineId={pipelineId}
            onConfirm={(edits) => handleConfirm("hitl_brief", edits)}
            onRevise={(fb) => handleRevise("hitl_brief", fb)}
          />
        )}

        {currentNode === "hitl_strategy" && (
          <HitlStrategy
            pipelineId={pipelineId}
            onConfirm={() => handleConfirm("hitl_strategy")}
            onRevise={(fb) => handleRevise("hitl_strategy", fb)}
          />
        )}

        {currentNode === "hitl_media" && (
          <HitlMedia
            pipelineId={pipelineId}
            onConfirm={(edits) => handleConfirm("hitl_media", edits)}
          />
        )}

        {currentNode === "hitl_structure" && (
          <HitlStructure
            pipelineId={pipelineId}
            onConfirm={(edits) => handleConfirm("hitl_structure", edits)}
          />
        )}

        {currentNode === "hitl_gallery" && <GalleryView />}

        {status === "completed" && (
          <div className="flex flex-col items-center justify-center h-full">
            <h2 className="text-2xl font-bold text-green-700">Proposal Ready</h2>
            <p className="mt-2 text-gray-600">Your PPT has been generated.</p>
            <div className="mt-6 flex gap-3">
              <a
                href={`/proposals/${pipelineId}`}
                className="px-4 py-2 bg-green-600 text-white rounded"
              >
                View & Download
              </a>
              <button
                onClick={() => dispatch(reset())}
                className="px-4 py-2 bg-blue-600 text-white rounded"
              >
                Start New Proposal
              </button>
            </div>
          </div>
        )}

        {status === "running" && !currentNode?.startsWith("hitl") && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full mx-auto" />
              <p className="mt-4 text-gray-600">Processing: {currentNode}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
