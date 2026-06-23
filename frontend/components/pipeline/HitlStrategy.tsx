"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useTranslations } from "next-intl";

interface Props {
  pipelineId: string;
  onConfirm: () => void;
  onRevise: (feedback: string, refreshResearch?: boolean) => void;
  onRerun: (rerunFrom: string, refreshResearch?: boolean) => void;
  disabled?: boolean;
}

const RERUN_NODE_KEYS = [
  "brief_analyzer",
  "research_agent",
  "strategy_phase1",
  "strategy_phase2",
] as const;

export function HitlStrategy({ pipelineId, onConfirm, onRevise, onRerun, disabled }: Props) {
  const t = useTranslations("pipeline");
  const th = useTranslations("pipeline.hitlStrategy");
  const [strategy, setStrategy] = useState<Record<string, unknown>>({});
  const [research, setResearch] = useState<Record<string, unknown>>({});
  const [brandCheckPassed, setBrandCheckPassed] = useState<boolean | null>(null);
  const [feedback, setFeedback] = useState("");
  const [refreshResearch, setRefreshResearch] = useState(false);
  const [showRerun, setShowRerun] = useState(false);
  const [rerunFrom, setRerunFrom] = useState("research_agent");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getStrategy(pipelineId).then((data) => {
      setStrategy((data.strategy_result as Record<string, unknown>) || {});
      setResearch((data.research_result as Record<string, unknown>) || {});
      setBrandCheckPassed(data.brand_check_passed as boolean | null);
      setLoading(false);
    });
  }, [pipelineId]);

  if (loading) {
    return <div className="p-8 text-center text-gray-500">{th("loading")}</div>;
  }

  const strategyOutput = (strategy.strategy_output as string) || "";

  return (
    <div className="max-w-4xl mx-auto p-8 overflow-y-auto h-full">
      <h2 className="text-xl font-bold mb-4">{t("hitlStrategy.title")}</h2>

      {brandCheckPassed === false && (
        <div className="bg-red-50 border border-red-200 rounded p-3 mb-4">
          <p className="text-sm text-red-700 font-medium">
            {t("hitlStrategy.brandIssue")}
          </p>
        </div>
      )}

      <div className="bg-white border rounded p-4 mb-6">
        <h3 className="text-sm font-semibold text-gray-500 mb-2">{t("hitlStrategy.strategyLabel")}</h3>
        <div className="text-sm text-gray-800 whitespace-pre-wrap">{strategyOutput}</div>
      </div>

      <details className="mb-6">
        <summary className="text-sm font-medium text-blue-600 cursor-pointer">
          {t("hitlStrategy.viewResearch")}
        </summary>
        <div className="mt-2 bg-gray-50 rounded p-4">
          <pre className="text-xs text-gray-700 whitespace-pre-wrap overflow-x-auto">
            {JSON.stringify(research, null, 2)}
          </pre>
        </div>
      </details>

      <div className="space-y-3 pt-4 border-t">
        {/* Row 1: Confirm */}
        <div className="flex items-center gap-3">
          <button
            onClick={onConfirm}
            disabled={disabled}
            className="px-4 py-2 bg-green-600 text-white rounded font-medium disabled:opacity-50"
          >
            {t("hitlStrategy.confirmStrategy")}
          </button>
        </div>

        {/* Row 2: Revise with feedback */}
        <div className="flex items-center gap-3">
          <input
            type="text"
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder={t("hitlStrategy.feedbackPlaceholder")}
            className="flex-1 border rounded px-3 py-2 text-sm"
          />
          <label className="flex items-center gap-1 text-xs text-gray-600 whitespace-nowrap">
            <input
              type="checkbox"
              checked={refreshResearch}
              onChange={(e) => setRefreshResearch(e.target.checked)}
              className="w-3.5 h-3.5"
            />
            {th("refreshResearch")}
          </label>
          <button
            onClick={() => { if (feedback.trim()) onRevise(feedback, refreshResearch); }}
            disabled={disabled || !feedback.trim()}
            className="px-4 py-2 bg-yellow-500 text-white rounded font-medium disabled:opacity-50"
          >
            {th("requestRevision")}
          </button>
        </div>

        {/* Row 3: Rerun (collapsed by default) */}
        <div>
          <button
            onClick={() => setShowRerun((v) => !v)}
            className="text-xs text-gray-500 underline"
          >
            {showRerun ? th("hideRerunOptions") : th("showRerunOptions")}
          </button>
          {showRerun && (
            <div className="mt-2 flex items-center gap-3 p-3 bg-gray-50 rounded border">
              <select
                value={rerunFrom}
                onChange={(e) => setRerunFrom(e.target.value)}
                className="border rounded px-2 py-1.5 text-sm"
              >
                {RERUN_NODE_KEYS.map((key) => (
                  <option key={key} value={key}>
                    {th(`rerunNodes.${key}` as Parameters<typeof th>[0])}
                  </option>
                ))}
              </select>
              <label className="flex items-center gap-1 text-xs text-gray-600">
                <input
                  type="checkbox"
                  checked={refreshResearch}
                  onChange={(e) => setRefreshResearch(e.target.checked)}
                  className="w-3.5 h-3.5"
                />
                {th("refreshResearch")}
              </label>
              <button
                onClick={() => onRerun(rerunFrom, refreshResearch)}
                disabled={disabled}
                className="px-3 py-1.5 bg-orange-500 text-white rounded text-sm font-medium disabled:opacity-50"
              >
                {th("rerun")}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
