"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface Props {
  pipelineId: string;
  onConfirm: () => void;
  onRevise: (feedback: string) => void;
}

export function HitlStrategy({ pipelineId, onConfirm, onRevise }: Props) {
  const [strategy, setStrategy] = useState<Record<string, unknown>>({});
  const [research, setResearch] = useState<Record<string, unknown>>({});
  const [brandCheckPassed, setBrandCheckPassed] = useState<boolean | null>(null);
  const [feedback, setFeedback] = useState("");
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
    return <div className="p-8 text-center text-gray-500">Loading strategy...</div>;
  }

  const strategyOutput = (strategy.strategy_output as string) || "";

  return (
    <div className="max-w-4xl mx-auto p-8 overflow-y-auto h-full">
      <h2 className="text-xl font-bold mb-4">Review Strategy</h2>

      {brandCheckPassed === false && (
        <div className="bg-red-50 border border-red-200 rounded p-3 mb-4">
          <p className="text-sm text-red-700 font-medium">
            Brand consistency check flagged potential issues.
          </p>
        </div>
      )}

      <div className="bg-white border rounded p-4 mb-6">
        <h3 className="text-sm font-semibold text-gray-500 mb-2">Strategy</h3>
        <div className="text-sm text-gray-800 whitespace-pre-wrap">{strategyOutput}</div>
      </div>

      <details className="mb-6">
        <summary className="text-sm font-medium text-blue-600 cursor-pointer">
          View Research Data
        </summary>
        <div className="mt-2 bg-gray-50 rounded p-4">
          <pre className="text-xs text-gray-700 whitespace-pre-wrap overflow-x-auto">
            {JSON.stringify(research, null, 2)}
          </pre>
        </div>
      </details>

      <div className="flex items-center gap-3 pt-4 border-t">
        <button
          onClick={onConfirm}
          className="px-4 py-2 bg-green-600 text-white rounded font-medium"
        >
          Confirm Strategy
        </button>
        <input
          type="text"
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          placeholder="Suggest changes..."
          className="flex-1 border rounded px-3 py-2 text-sm"
        />
        <button
          onClick={() => {
            if (feedback.trim()) onRevise(feedback);
          }}
          className="px-4 py-2 bg-yellow-500 text-white rounded font-medium"
        >
          Request Revision
        </button>
      </div>
    </div>
  );
}
