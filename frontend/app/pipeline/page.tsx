"use client";

import { useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
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
import { useTranslations } from "next-intl";

type StartHandler = (brief: string, clientId: string, projectId: string, outputLanguage: string) => void;

function BriefInputWithParams({ onSubmit }: { onSubmit: StartHandler }) {
  const searchParams = useSearchParams();
  const initialClientId = searchParams.get("client_id") ?? undefined;
  const initialProjectId = searchParams.get("project_id") ?? undefined;
  return (
    <BriefInput
      onSubmit={onSubmit}
      initialClientId={initialClientId}
      initialProjectId={initialProjectId}
    />
  );
}

export default function PipelinePage() {
  const t = useTranslations("pipeline");
  const dispatch = useDispatch();
  const { pipelineId, status, currentNode } = useSelector(
    (state: RootState) => state.pipeline
  );
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);

  // WebSocket is receive-only: dispatches Redux actions on progress events
  usePipelineSocket(pipelineId);

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
      setError(err instanceof Error ? err.message : t("startError"));
    }
  };

  const handleConfirm = async (node: string, edits?: Record<string, unknown>) => {
    if (!pipelineId || confirming) return;
    setConfirming(true);
    try {
      await api.confirmNode(pipelineId, { node, action: "confirm", edits });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t("confirmError"));
    } finally {
      setConfirming(false);
    }
  };

  const handleRevise = async (node: string, feedback: string, refreshResearch?: boolean) => {
    if (!pipelineId || confirming) return;
    setConfirming(true);
    try {
      await api.confirmNode(pipelineId, {
        node,
        action: "revise",
        feedback,
        refresh_research: refreshResearch,
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t("confirmError"));
    } finally {
      setConfirming(false);
    }
  };

  const handleRerun = async (node: string, rerunFrom: string, refreshResearch?: boolean) => {
    if (!pipelineId || confirming) return;
    setConfirming(true);
    try {
      await api.confirmNode(pipelineId, {
        node,
        action: "rerun",
        rerun_from: rerunFrom,
        refresh_research: refreshResearch,
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t("confirmError"));
    } finally {
      setConfirming(false);
    }
  };

  if (!pipelineId) {
    return (
      <div className="max-w-3xl mx-auto p-8">
        <h1 className="text-2xl font-bold mb-6">{t("title")}</h1>
        <Suspense fallback={<BriefInput onSubmit={handleStart} />}>
          <BriefInputWithParams onSubmit={handleStart} />
        </Suspense>
        {error && <p className="mt-4 text-red-600 text-sm">{error}</p>}
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col">
      <PipelineProgress currentNode={currentNode} status={status} />

      {error && (
        <div className="bg-red-50 border-b border-red-200 px-4 py-2 text-sm text-red-700">
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">dismiss</button>
        </div>
      )}

      <div className="flex-1 overflow-hidden">
        {currentNode === "hitl_brief" && (
          <HitlBrief
            pipelineId={pipelineId}
            onConfirm={(edits) => handleConfirm("hitl_brief", edits)}
            onRevise={(fb) => handleRevise("hitl_brief", fb)}
            disabled={confirming}
          />
        )}

        {currentNode === "hitl_strategy" && (
          <HitlStrategy
            pipelineId={pipelineId}
            onConfirm={() => handleConfirm("hitl_strategy")}
            onRevise={(fb, refresh) => handleRevise("hitl_strategy", fb, refresh)}
            onRerun={(rerunFrom, refresh) => handleRerun("hitl_strategy", rerunFrom, refresh)}
            disabled={confirming}
          />
        )}

        {currentNode === "hitl_media" && (
          <HitlMedia
            pipelineId={pipelineId}
            onConfirm={(edits) => handleConfirm("hitl_media", edits)}
            disabled={confirming}
          />
        )}

        {currentNode === "hitl_structure" && (
          <HitlStructure
            pipelineId={pipelineId}
            onConfirm={(edits) => handleConfirm("hitl_structure", edits)}
            disabled={confirming}
          />
        )}

        {currentNode === "hitl_gallery" && <GalleryView />}

        {status === "completed" && (
          <div className="flex flex-col items-center justify-center h-full">
            <h2 className="text-2xl font-bold text-green-700">{t("proposalReady")}</h2>
            <p className="mt-2 text-gray-600">{t("proposalReadyDesc")}</p>
            <div className="mt-6 flex gap-3">
              <a
                href={`/proposals/${pipelineId}`}
                className="px-4 py-2 bg-green-600 text-white rounded"
              >
                {t("viewDownload")}
              </a>
              <button
                onClick={() => dispatch(reset())}
                className="px-4 py-2 bg-blue-600 text-white rounded"
              >
                {t("startNew")}
              </button>
            </div>
          </div>
        )}

        {status === "running" && !currentNode?.startsWith("hitl") && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full mx-auto" />
              <p className="mt-4 text-gray-600">{t("processing")} {currentNode}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
