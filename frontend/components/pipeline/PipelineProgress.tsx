"use client";

import { useTranslations } from "next-intl";

interface Props {
  currentNode: string | null;
  status: string;
}

export function PipelineProgress({ currentNode, status }: Props) {
  const t = useTranslations("pipeline");

  const STAGES = [
    { id: "brief_analyzer", label: t("progress.brief") },
    { id: "research_agent", label: t("progress.research") },
    { id: "strategy_phase1", label: t("progress.strategy") },
    { id: "media_planner", label: t("progress.mediaPlan") },
    { id: "resource_agent", label: t("progress.resources") },
    { id: "deck_orchestrator", label: t("progress.deck") },
    { id: "slide_content", label: t("progress.slides") },
    { id: "ppt_builder", label: t("progress.ppt") },
  ];

  const NODE_TO_STAGE: Record<string, string> = {
    brief_analyzer: "brief_analyzer",
    hitl_brief: "brief_analyzer",
    research_agent: "research_agent",
    strategy_phase1: "strategy_phase1",
    strategy_phase2: "strategy_phase1",
    brand_check: "strategy_phase1",
    hitl_strategy: "strategy_phase1",
    media_planner: "media_planner",
    hitl_media: "media_planner",
    resource_agent: "resource_agent",
    deck_orchestrator: "deck_orchestrator",
    hitl_structure: "deck_orchestrator",
    slide_content: "slide_content",
    narrative_agent: "slide_content",
    hitl_gallery: "slide_content",
    ppt_builder: "ppt_builder",
  };

  const activeStage = currentNode ? NODE_TO_STAGE[currentNode] : null;
  const activeIdx = STAGES.findIndex((s) => s.id === activeStage);

  return (
    <div className="border-b bg-white px-6 py-3">
      <div className="flex items-center gap-2">
        {STAGES.map((stage, i) => {
          const isActive = stage.id === activeStage;
          const isDone = activeIdx > i || status === "completed";
          return (
            <div key={stage.id} className="flex items-center gap-2">
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium ${
                  isDone
                    ? "bg-green-600 text-white"
                    : isActive
                      ? "bg-blue-600 text-white"
                      : "bg-gray-200 text-gray-500"
                }`}
              >
                {isDone ? "✓" : i + 1}
              </div>
              <span
                className={`text-xs ${
                  isActive ? "font-semibold text-blue-700" : "text-gray-500"
                }`}
              >
                {stage.label}
              </span>
              {i < STAGES.length - 1 && (
                <div className={`w-8 h-0.5 ${isDone ? "bg-green-400" : "bg-gray-200"}`} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
