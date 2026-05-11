"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface MediaTier {
  tier: string;
  channel: string;
  role: string;
  count: number;
  budget_percentage: number;
  budget_absolute: number | null;
  selection_criteria: string;
  platform_rationale: string;
}

interface MediaPlanData {
  tiers: MediaTier[];
  strategy_interpretation: string | null;
  rationale: string | null;
  historical_references: string[];
}

interface Props {
  pipelineId: string;
  onConfirm: (edits?: Record<string, unknown>) => void;
}

const ROLE_LABELS: Record<string, string> = {
  awareness: "声量",
  amplification: "扩散",
  ugc: "UGC",
  credibility: "公信力",
};

export function HitlMedia({ pipelineId, onConfirm }: Props) {
  const [plan, setPlan] = useState<MediaPlanData | null>(null);
  const [tiers, setTiers] = useState<MediaTier[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getMediaPlan(pipelineId).then((data) => {
      const mediaPlan = data.media_plan as MediaPlanData;
      setPlan(mediaPlan);
      setTiers(mediaPlan?.tiers || []);
      setLoading(false);
    });
  }, [pipelineId]);

  const updateTier = (index: number, field: keyof MediaTier, value: unknown) => {
    setTiers((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], [field]: value };
      return updated;
    });
  };

  const handleConfirm = () => {
    const edits = { media_plan: { ...plan, tiers } };
    onConfirm(edits);
  };

  if (loading) {
    return <div className="p-8 text-center text-gray-500">Generating media plan...</div>;
  }

  if (!plan) {
    return <div className="p-8 text-center text-red-500">Failed to load media plan.</div>;
  }

  return (
    <div className="max-w-5xl mx-auto p-8 overflow-y-auto h-full">
      <h2 className="text-xl font-bold mb-2">Review Media Plan</h2>

      {plan.strategy_interpretation && (
        <div className="bg-blue-50 border border-blue-200 rounded p-3 mb-4 text-sm text-blue-800">
          <span className="font-medium">Strategy Interpretation: </span>
          {plan.strategy_interpretation}
        </div>
      )}

      {plan.rationale && (
        <p className="text-sm text-gray-600 mb-4">{plan.rationale}</p>
      )}

      <div className="overflow-x-auto mb-6">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-gray-50">
              <th className="border px-3 py-2 text-left">Channel</th>
              <th className="border px-3 py-2 text-left">Tier</th>
              <th className="border px-3 py-2 text-center w-20">Count</th>
              <th className="border px-3 py-2 text-center w-24">Budget %</th>
              <th className="border px-3 py-2 text-center w-28">Amount</th>
              <th className="border px-3 py-2 text-left">Role</th>
              <th className="border px-3 py-2 text-left">Selection Criteria</th>
            </tr>
          </thead>
          <tbody>
            {tiers.map((t, i) => (
              <tr key={i} className="hover:bg-gray-50">
                <td className="border px-3 py-2">{t.channel}</td>
                <td className="border px-3 py-2">{t.tier}</td>
                <td className="border px-2 py-1 text-center">
                  <input
                    type="number"
                    min={0}
                    value={t.count}
                    onChange={(e) => updateTier(i, "count", parseInt(e.target.value) || 0)}
                    className="w-16 border rounded px-1 py-0.5 text-center text-sm"
                  />
                </td>
                <td className="border px-2 py-1 text-center">
                  <input
                    type="number"
                    min={0}
                    max={100}
                    step={5}
                    value={t.budget_percentage}
                    onChange={(e) => updateTier(i, "budget_percentage", parseFloat(e.target.value) || 0)}
                    className="w-16 border rounded px-1 py-0.5 text-center text-sm"
                  />
                  <span className="text-gray-400 ml-0.5">%</span>
                </td>
                <td className="border px-3 py-2 text-center text-gray-500">
                  {t.budget_absolute != null ? `¥${t.budget_absolute.toLocaleString()}` : "—"}
                </td>
                <td className="border px-3 py-2">
                  <span className="text-xs bg-gray-100 px-1.5 py-0.5 rounded">
                    {ROLE_LABELS[t.role] || t.role}
                  </span>
                </td>
                <td className="border px-3 py-2 text-xs text-gray-600 max-w-xs">
                  {t.selection_criteria}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {plan.historical_references.length > 0 && (
        <details className="mb-6">
          <summary className="text-sm font-medium text-blue-600 cursor-pointer">
            Historical References ({plan.historical_references.length})
          </summary>
          <ul className="mt-2 text-xs text-gray-600 space-y-1 pl-4 list-disc">
            {plan.historical_references.map((ref, i) => (
              <li key={i}>{ref}</li>
            ))}
          </ul>
        </details>
      )}

      <div className="flex items-center gap-3 pt-4 border-t">
        <button
          onClick={handleConfirm}
          className="px-5 py-2 bg-green-600 text-white rounded font-medium hover:bg-green-700"
        >
          Confirm Media Plan
        </button>
        <span className="text-xs text-gray-500">
          You can adjust count and budget % above before confirming.
        </span>
      </div>
    </div>
  );
}
