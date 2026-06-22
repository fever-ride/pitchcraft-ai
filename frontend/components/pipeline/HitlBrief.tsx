"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useTranslations } from "next-intl";

interface Props {
  pipelineId: string;
  onConfirm: (edits?: Record<string, unknown>) => void;
  onRevise: (feedback: string) => void;
  disabled?: boolean;
}

export function HitlBrief({ pipelineId, onConfirm, onRevise, disabled }: Props) {
  const t = useTranslations("pipeline");
  const [brief, setBrief] = useState<Record<string, unknown>>({});
  const [rawBrief, setRawBrief] = useState("");
  const [feedback, setFeedback] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getBrief(pipelineId).then((data) => {
      setBrief(data.structured_brief || {});
      setRawBrief(data.raw_brief || "");
      setLoading(false);
    });
  }, [pipelineId]);

  if (loading) {
    return <div className="p-8 text-center text-gray-500">{t("hitlBrief.loading")}</div>;
  }

  const fieldKeys = [
    "client_name",
    "theme",
    "audience",
    "channels",
    "budget",
    "timeline",
    "objective",
    "competitors",
  ] as const;

  return (
    <div className="max-w-3xl mx-auto p-8">
      <h2 className="text-xl font-bold mb-4">{t("hitlBrief.title")}</h2>

      <div className="bg-gray-50 rounded p-4 mb-6">
        <h3 className="text-sm font-semibold text-gray-500 mb-2">{t("hitlBrief.originalBrief")}</h3>
        <p className="text-sm text-gray-700 whitespace-pre-wrap">{rawBrief}</p>
      </div>

      <div className="space-y-3 mb-6">
        {fieldKeys.map((key) => {
          const value = brief[key];
          // Skip empty arrays (e.g. competitors when not mentioned)
          if (Array.isArray(value) && value.length === 0) return null;
          const display = Array.isArray(value) ? value.join(", ") : String(value || "—");
          return (
            <div key={key} className="flex items-start">
              <span className="w-28 shrink-0 text-sm font-medium text-gray-500">{t(`hitlBrief.fields.${key}`)}</span>
              <span className="text-sm text-gray-800">{display}</span>
            </div>
          );
        })}
      </div>

      {!!(brief as Record<string, unknown>).missing_fields && (
        <div className="bg-amber-50 border border-amber-200 rounded p-3 mb-6">
          <h4 className="text-sm font-semibold text-amber-800 mb-1">{t("hitlBrief.missingInfo")}</h4>
          <ul className="text-sm text-amber-700 list-disc pl-4">
            {((brief as Record<string, unknown>).missing_fields as string[]).map((f, i) => (
              <li key={i}>{f}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex items-center gap-3 pt-4 border-t">
        <button
          onClick={() => onConfirm()}
          disabled={disabled}
          className="px-4 py-2 bg-green-600 text-white rounded font-medium disabled:opacity-50"
        >
          {t("hitlBrief.confirmBrief")}
        </button>
        <input
          type="text"
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          placeholder={t("hitlBrief.feedbackPlaceholder")}
          className="flex-1 border rounded px-3 py-2 text-sm"
        />
        <button
          onClick={() => { if (feedback.trim()) onRevise(feedback); }}
          disabled={disabled || !feedback.trim()}
          className="px-4 py-2 bg-yellow-500 text-white rounded font-medium disabled:opacity-50"
        >
          {t("hitlBrief.revise")}
        </button>
      </div>
    </div>
  );
}
