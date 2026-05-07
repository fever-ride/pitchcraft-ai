"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface Props {
  pipelineId: string;
  onConfirm: (edits?: Record<string, unknown>) => void;
  onRevise: (feedback: string) => void;
}

export function HitlBrief({ pipelineId, onConfirm, onRevise }: Props) {
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
    return <div className="p-8 text-center text-gray-500">Loading brief analysis...</div>;
  }

  const fields = [
    { key: "client_name", label: "Client" },
    { key: "theme", label: "Theme" },
    { key: "audience", label: "Audience" },
    { key: "channels", label: "Channels" },
    { key: "budget", label: "Budget" },
    { key: "timeline", label: "Timeline" },
    { key: "objective", label: "Objective" },
  ];

  return (
    <div className="max-w-3xl mx-auto p-8">
      <h2 className="text-xl font-bold mb-4">Review Parsed Brief</h2>

      <div className="bg-gray-50 rounded p-4 mb-6">
        <h3 className="text-sm font-semibold text-gray-500 mb-2">Original Brief</h3>
        <p className="text-sm text-gray-700 whitespace-pre-wrap">{rawBrief}</p>
      </div>

      <div className="space-y-3 mb-6">
        {fields.map(({ key, label }) => {
          const value = brief[key];
          const display = Array.isArray(value) ? value.join(", ") : String(value || "—");
          return (
            <div key={key} className="flex items-start">
              <span className="w-24 text-sm font-medium text-gray-500">{label}</span>
              <span className="text-sm text-gray-800">{display}</span>
            </div>
          );
        })}
      </div>

      {(brief as Record<string, unknown>).missing_fields && (
        <div className="bg-amber-50 border border-amber-200 rounded p-3 mb-6">
          <h4 className="text-sm font-semibold text-amber-800 mb-1">Missing Information</h4>
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
          className="px-4 py-2 bg-green-600 text-white rounded font-medium"
        >
          Confirm Brief
        </button>
        <input
          type="text"
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          placeholder="Add clarification or corrections..."
          className="flex-1 border rounded px-3 py-2 text-sm"
        />
        <button
          onClick={() => {
            if (feedback.trim()) onRevise(feedback);
          }}
          className="px-4 py-2 bg-yellow-500 text-white rounded font-medium"
        >
          Revise
        </button>
      </div>
    </div>
  );
}
