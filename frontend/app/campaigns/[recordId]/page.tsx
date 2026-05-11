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
        {MODULE_ORDER.map((moduleName) => (
          <ModuleSection
            key={moduleName}
            name={moduleName}
            data={currentRecord[moduleName] as Record<string, unknown> | undefined}
            edits={edits}
            onEdit={handleEdit}
            isPending={isPending}
          />
        ))}
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
