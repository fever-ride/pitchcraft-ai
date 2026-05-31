"use client";

import { useParams, useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import { useDispatch, useSelector } from "react-redux";

import type { AppDispatch, RootState } from "@/store/store";
import {
  fetchRecord,
  confirmRecord,
  setEdit,
  clearCurrentRecord,
} from "@/store/campaignsSlice";
import { addToast } from "@/store/toastSlice";

type ModuleName =
  | "meta"
  | "strategy_decisions"
  | "communication_plan"
  | "media_plan"
  | "execution"
  | "outcome"
  | "client_learnings"
  | "deck_info";

const CAMPAIGN_TYPES = ["launch", "branding", "conversion", "event", "crisis", "always_on", "other"];
const BUDGET_TIERS = ["under_100k", "100k_500k", "500k_2m", "2m_5m", "above_5m"];

const ENUM_FIELDS: Record<string, string[]> = {
  "meta.campaign_type": CAMPAIGN_TYPES,
  "meta.budget_tier": BUDGET_TIERS,
};

function StarRating({ value, onChange, readonly }: { value: number | null; onChange?: (v: number) => void; readonly?: boolean }) {
  return (
    <div className="flex gap-1">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          disabled={readonly}
          onClick={() => onChange?.(star)}
          className={`text-lg ${star <= (value || 0) ? "text-yellow-400" : "text-gray-300"} ${readonly ? "cursor-default" : "cursor-pointer hover:text-yellow-500"}`}
        >
          ★
        </button>
      ))}
    </div>
  );
}

const PITCH_OUTCOME_OPTIONS = ["won", "lost", "unknown"] as const;
type PitchOutcome = (typeof PITCH_OUTCOME_OPTIONS)[number];

const PITCH_OUTCOME_LABELS: Record<PitchOutcome, string> = {
  won: "Won ✓",
  lost: "Lost ✗",
  unknown: "Unknown",
};

const MODULE_LABELS: Record<ModuleName, string> = {
  meta: "Campaign Meta",
  strategy_decisions: "Strategy Decisions",
  communication_plan: "Communication Plan",
  media_plan: "Media Plan",
  execution: "Execution Details",
  outcome: "Outcome & Results",
  client_learnings: "Client Learnings",
  deck_info: "Deck Info",
};

const MODULE_ORDER: ModuleName[] = [
  "meta",
  "strategy_decisions",
  "communication_plan",
  "media_plan",
  "execution",
  "outcome",
  "client_learnings",
  "deck_info",
];

function ConfidenceIndicator({ confidence }: { confidence: string }) {
  const colors: Record<string, string> = {
    high: "text-green-600",
    partial: "text-yellow-600",
    low: "text-red-600",
  };
  return (
    <span className={`text-sm font-medium ${colors[confidence] || "text-gray-500"}`}>
      Confidence: {confidence}
    </span>
  );
}

function ModuleSection({
  name,
  data,
  edits,
  onEdit,
  isPending,
}: {
  name: ModuleName;
  data: Record<string, unknown> | undefined;
  edits: Record<string, unknown>;
  onEdit: (key: string, value: unknown) => void;
  isPending: boolean;
}) {
  const [expanded, setExpanded] = useState(name === "meta" || name === "strategy_decisions");

  if (!data || Object.keys(data).length === 0) {
    return (
      <div className="border rounded p-4 opacity-60">
        <div className="flex items-center justify-between">
          <h3 className="font-medium text-sm text-gray-500">{MODULE_LABELS[name]}</h3>
          <span className="text-xs text-gray-400">No data extracted</span>
        </div>
      </div>
    );
  }

  return (
    <div className="border rounded p-4">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between"
      >
        <h3 className="font-medium text-sm">{MODULE_LABELS[name]}</h3>
        <span className="text-gray-400 text-xs">{expanded ? "collapse" : "expand"}</span>
      </button>
      {expanded && (
        <div className="mt-3 space-y-2">
          {Object.entries(data).map(([field, value]) => {
            if (value === null || value === undefined) return null;
            if (field === "budget_missing") return null;

            const editKey = `${name}.${field}`;
            const currentValue = edits[editKey] !== undefined ? edits[editKey] : value;
            const isEdited = edits[editKey] !== undefined;

            // Enum fields: render as dropdown
            const enumOptions = ENUM_FIELDS[editKey];
            if (enumOptions && isPending) {
              return (
                <div key={field} className="text-sm">
                  <label className="text-xs text-gray-500 block mb-1">
                    {field.replace(/_/g, " ")}
                    {isEdited && <span className="ml-1 text-blue-500">(edited)</span>}
                  </label>
                  <select
                    value={String(currentValue ?? "")}
                    onChange={(e) => onEdit(editKey, e.target.value)}
                    className="w-full border rounded px-2 py-1 text-sm"
                  >
                    <option value="">-- select --</option>
                    {enumOptions.map((opt) => (
                      <option key={opt} value={opt}>{opt.replace(/_/g, " ")}</option>
                    ))}
                  </select>
                </div>
              );
            }

            if (Array.isArray(value) || (typeof value === "object" && value !== null)) {
              return (
                <div key={field} className="text-sm">
                  <label className="text-xs text-gray-500 block mb-1">
                    {field.replace(/_/g, " ")}
                    {isEdited && <span className="ml-1 text-blue-500">(edited)</span>}
                  </label>
                  {isPending ? (
                    <textarea
                      value={JSON.stringify(currentValue, null, 2)}
                      onChange={(e) => {
                        try {
                          onEdit(editKey, JSON.parse(e.target.value));
                        } catch {
                          // invalid JSON, ignore until valid
                        }
                      }}
                      className="w-full border rounded px-2 py-1 text-sm font-mono min-h-[60px]"
                    />
                  ) : (
                    <pre className="text-xs bg-gray-50 rounded p-2 overflow-x-auto">
                      {JSON.stringify(value, null, 2)}
                    </pre>
                  )}
                </div>
              );
            }

            return (
              <div key={field} className="text-sm">
                <label className="text-xs text-gray-500 block mb-1">
                  {field.replace(/_/g, " ")}
                  {isEdited && <span className="ml-1 text-blue-500">(edited)</span>}
                </label>
                {isPending ? (
                  <input
                    type="text"
                    value={String(currentValue ?? "")}
                    onChange={(e) => onEdit(editKey, e.target.value)}
                    className="w-full border rounded px-2 py-1 text-sm"
                  />
                ) : (
                  <span className="text-gray-800">{String(value)}</span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function ClientLearningsSection({
  data,
  edits,
  onEdit,
  isPending,
}: {
  data: Record<string, unknown> | undefined;
  edits: Record<string, unknown>;
  onEdit: (key: string, value: unknown) => void;
  isPending: boolean;
}) {
  const [expanded, setExpanded] = useState(false);

  const getValue = (field: string) => {
    const editKey = `client_learnings.${field}`;
    if (edits[editKey] !== undefined) return edits[editKey];
    return data?.[field] ?? "";
  };

  const getListValue = (field: string): string[] => {
    const editKey = `client_learnings.${field}`;
    const val = edits[editKey] !== undefined ? edits[editKey] : data?.[field];
    if (Array.isArray(val)) return val;
    return [];
  };

  const handleListChange = (field: string, index: number, value: string) => {
    const list = [...getListValue(field)];
    list[index] = value;
    onEdit(`client_learnings.${field}`, list);
  };

  const handleListAdd = (field: string) => {
    onEdit(`client_learnings.${field}`, [...getListValue(field), ""]);
  };

  const handleListRemove = (field: string, index: number) => {
    const list = getListValue(field).filter((_, i) => i !== index);
    onEdit(`client_learnings.${field}`, list);
  };

  return (
    <div className="border rounded p-4">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between"
      >
        <div className="flex items-center gap-2">
          <h3 className="font-medium text-sm">Client Learnings</h3>
          <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded">
            Manual — AE fills after project
          </span>
        </div>
        <span className="text-gray-400 text-xs">{expanded ? "collapse" : "expand"}</span>
      </button>

      {expanded && (
        <div className="mt-3 space-y-4">
          {/* Decision Style */}
          <div>
            <label className="text-xs text-gray-500 block mb-1">
              Decision style <span className="text-gray-400">(How this client evaluates and approves work)</span>
            </label>
            {isPending ? (
              <textarea
                value={String(getValue("decision_style") ?? "")}
                onChange={(e) => onEdit("client_learnings.decision_style", e.target.value)}
                placeholder="e.g. Prefers bold creative, risk-averse on budget, likes to see 3 options before deciding"
                className="w-full border rounded px-2 py-1 text-sm min-h-[60px] resize-y"
              />
            ) : (
              <p className="text-sm text-gray-800 whitespace-pre-wrap">
                {String(getValue("decision_style") || "—")}
              </p>
            )}
          </div>

          {/* Approved Directions */}
          <div>
            <label className="text-xs text-gray-500 block mb-1">
              Approved directions <span className="text-gray-400">(What the client liked and signed off on)</span>
            </label>
            {isPending ? (
              <div className="space-y-1">
                {getListValue("client_approved_directions").map((item, i) => (
                  <div key={i} className="flex gap-1">
                    <input
                      type="text"
                      value={item}
                      onChange={(e) => handleListChange("client_approved_directions", i, e.target.value)}
                      className="flex-1 border rounded px-2 py-1 text-sm"
                    />
                    <button
                      type="button"
                      onClick={() => handleListRemove("client_approved_directions", i)}
                      className="text-gray-400 hover:text-red-500 px-1 text-xs"
                    >
                      ✕
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => handleListAdd("client_approved_directions")}
                  className="text-xs text-blue-600 hover:underline"
                >
                  + Add direction
                </button>
              </div>
            ) : (
              <ul className="text-sm text-gray-800 list-disc list-inside space-y-0.5">
                {getListValue("client_approved_directions").length > 0
                  ? getListValue("client_approved_directions").map((item, i) => <li key={i}>{item}</li>)
                  : <li className="text-gray-400 list-none">—</li>}
              </ul>
            )}
          </div>

          {/* Rejected Directions */}
          <div>
            <label className="text-xs text-gray-500 block mb-1">
              Rejected directions <span className="text-gray-400">(What the client pushed back on — avoid in future)</span>
            </label>
            {isPending ? (
              <div className="space-y-1">
                {getListValue("client_rejected_directions").map((item, i) => (
                  <div key={i} className="flex gap-1">
                    <input
                      type="text"
                      value={item}
                      onChange={(e) => handleListChange("client_rejected_directions", i, e.target.value)}
                      className="flex-1 border rounded px-2 py-1 text-sm"
                    />
                    <button
                      type="button"
                      onClick={() => handleListRemove("client_rejected_directions", i)}
                      className="text-gray-400 hover:text-red-500 px-1 text-xs"
                    >
                      ✕
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => handleListAdd("client_rejected_directions")}
                  className="text-xs text-blue-600 hover:underline"
                >
                  + Add direction
                </button>
              </div>
            ) : (
              <ul className="text-sm text-gray-800 list-disc list-inside space-y-0.5">
                {getListValue("client_rejected_directions").length > 0
                  ? getListValue("client_rejected_directions").map((item, i) => <li key={i}>{item}</li>)
                  : <li className="text-gray-400 list-none">—</li>}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function CampaignDetailPage() {
  const params = useParams();
  const router = useRouter();
  const dispatch = useDispatch<AppDispatch>();
  const recordId = params.recordId as string;

  const { currentRecord, edits, loading, confirming, error } = useSelector(
    (state: RootState) => state.campaigns
  );

  useEffect(() => {
    dispatch(fetchRecord(recordId));
    return () => {
      dispatch(clearCurrentRecord());
    };
  }, [dispatch, recordId]);

  const handleEdit = (key: string, value: unknown) => {
    dispatch(setEdit({ key, value }));
  };

  const handleConfirm = async () => {
    const result = await dispatch(confirmRecord({ recordId, edits }));
    if (confirmRecord.fulfilled.match(result)) {
      dispatch(addToast({ message: "Record confirmed. Proposition indexing started.", type: "success" }));
      router.push("/campaigns");
    }
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto p-8">
        <p className="text-gray-500">Loading...</p>
      </div>
    );
  }

  if (error && !currentRecord) {
    return (
      <div className="max-w-4xl mx-auto p-8">
        <p className="text-red-500">{error}</p>
      </div>
    );
  }

  if (!currentRecord) return null;

  const isPending = currentRecord.status === "pending_confirmation";

  return (
    <div className="max-w-4xl mx-auto p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <button onClick={() => router.back()} className="text-sm text-blue-600 hover:underline mb-2">
            &larr; Back to list
          </button>
          <h1 className="text-xl font-bold">Campaign Record Review</h1>
        </div>
        <div className="flex items-center gap-3">
          <ConfidenceIndicator confidence={currentRecord.confidence} />
          <span className={`text-xs px-2 py-1 rounded ${isPending ? "bg-orange-100 text-orange-700" : "bg-green-100 text-green-700"}`}>
            {isPending ? "Pending Confirmation" : "Confirmed"}
          </span>
        </div>
      </div>

      {currentRecord.confidence === "low" && (
        <div className="bg-red-50 border border-red-200 rounded p-3 mb-4 text-sm text-red-700">
          Low confidence extraction. Please review all fields carefully before confirming.
        </div>
      )}

      {currentRecord.confidence === "partial" && (
        <div className="bg-yellow-50 border border-yellow-200 rounded p-3 mb-4 text-sm text-yellow-700">
          Partial confidence. Some fields may be incomplete or inferred. Review highlighted sections.
        </div>
      )}

      <div className="space-y-4 mb-8">
        {MODULE_ORDER.map((moduleName) => {
          if (moduleName === "client_learnings") {
            return (
              <ClientLearningsSection
                key="client_learnings"
                data={currentRecord.client_learnings as Record<string, unknown> | undefined}
                edits={edits}
                onEdit={handleEdit}
                isPending={isPending}
              />
            );
          }
          return (
            <ModuleSection
              key={moduleName}
              name={moduleName}
              data={currentRecord[moduleName] as Record<string, unknown> | undefined}
              edits={edits}
              onEdit={handleEdit}
              isPending={isPending}
            />
          );
        })}
      </div>

      {error && <p className="text-red-500 text-sm mb-4">{error}</p>}

      {isPending && (
        <div className="sticky bottom-0 bg-white border-t p-4 -mx-8 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div>
              <span className="text-xs text-gray-500 block mb-1">Overall Rating</span>
              <StarRating
                value={edits["outcome.overall_rating"] as number | null}
                onChange={(v) => handleEdit("outcome.overall_rating", v)}
              />
            </div>
            {currentRecord.record_type === "proposal" && (
              <div>
                <span className="text-xs text-gray-500 block mb-1">Pitch Outcome</span>
                <div className="flex gap-1">
                  {PITCH_OUTCOME_OPTIONS.map((opt) => {
                    const current =
                      (edits["pitch_outcome"] as PitchOutcome | undefined) ??
                      (currentRecord.pitch_outcome as PitchOutcome | undefined) ??
                      "unknown";
                    return (
                      <button
                        key={opt}
                        type="button"
                        onClick={() => handleEdit("pitch_outcome", opt)}
                        className={`px-2 py-1 text-xs rounded border transition-colors ${
                          current === opt
                            ? opt === "won"
                              ? "bg-green-100 border-green-400 text-green-700 font-medium"
                              : opt === "lost"
                              ? "bg-red-100 border-red-400 text-red-700 font-medium"
                              : "bg-gray-100 border-gray-400 text-gray-700 font-medium"
                            : "border-gray-200 text-gray-400 hover:border-gray-400"
                        }`}
                      >
                        {PITCH_OUTCOME_LABELS[opt]}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
            <div className="text-sm text-gray-500">
              {Object.keys(edits).length > 0
                ? `${Object.keys(edits).length} field(s) edited`
                : "Review complete? Confirm to enable retrieval."}
            </div>
          </div>
          <button
            onClick={handleConfirm}
            disabled={confirming}
            className="px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 text-sm font-medium"
          >
            {confirming ? "Confirming..." : "Confirm Record"}
          </button>
        </div>
      )}
    </div>
  );
}
