"use client";

import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";

interface VersionSummary {
  _id: string;
  version: number;
  trigger: string;
  note: string;
  created_at: string;
}

interface VersionDiff {
  changed_fields: string[];
  diff: Record<string, { v1: unknown; v2: unknown }>;
}

interface Props {
  proposalId: string;
  onRollback?: () => void;
}

export default function VersionPanel({ proposalId, onRollback }: Props) {
  const [versions, setVersions] = useState<VersionSummary[]>([]);
  const [selectedV1, setSelectedV1] = useState<number | null>(null);
  const [selectedV2, setSelectedV2] = useState<number | null>(null);
  const [diff, setDiff] = useState<VersionDiff | null>(null);
  const [editingNote, setEditingNote] = useState<number | null>(null);
  const [noteText, setNoteText] = useState("");
  const [rolling, setRolling] = useState(false);

  const loadVersions = async () => {
    const res = await apiFetch(`/api/v1/proposals/${proposalId}/versions`);
    if (res.ok) {
      const data = await res.json();
      setVersions(data.sort((a: VersionSummary, b: VersionSummary) => b.version - a.version));
    }
  };

  useEffect(() => {
    loadVersions();
  }, [proposalId]);

  const loadDiff = async (v1: number, v2: number) => {
    const res = await apiFetch(`/api/v1/proposals/${proposalId}/versions/${v1}/diff/${v2}`);
    if (res.ok) {
      setDiff(await res.json());
    }
  };

  const handleCompare = () => {
    if (selectedV1 !== null && selectedV2 !== null && selectedV1 !== selectedV2) {
      loadDiff(selectedV1, selectedV2);
    }
  };

  const handleRollback = async (version: number) => {
    if (!confirm(`Roll back to version ${version}? This creates a new version from the old state.`)) return;
    setRolling(true);
    const res = await apiFetch(
      `/api/v1/proposals/${proposalId}/versions/${version}/rollback`,
      { method: "POST" }
    );
    setRolling(false);
    if (res.ok) {
      await loadVersions();
      setDiff(null);
      onRollback?.();
    }
  };

  const handleSaveNote = async (version: number) => {
    await apiFetch(`/api/v1/proposals/${proposalId}/versions/${version}/note`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note: noteText }),
    });
    setEditingNote(null);
    loadVersions();
  };

  const triggerLabel = (trigger: string) => {
    if (trigger === "pipeline_complete") return "Initial";
    if (trigger === "rerun") return "Rerun";
    if (trigger.startsWith("rollback")) return "Rollback";
    return trigger;
  };

  const triggerColor = (trigger: string) => {
    if (trigger === "pipeline_complete") return "bg-green-100 text-green-700";
    if (trigger === "rerun") return "bg-blue-100 text-blue-700";
    if (trigger.startsWith("rollback")) return "bg-orange-100 text-orange-700";
    return "bg-gray-100 text-gray-700";
  };

  if (versions.length === 0) {
    return (
      <div className="border rounded p-4">
        <h3 className="font-semibold text-sm mb-2">Versions</h3>
        <p className="text-xs text-gray-500">No versions saved yet.</p>
      </div>
    );
  }

  return (
    <div className="border rounded p-4">
      <h3 className="font-semibold text-sm mb-3">Version History</h3>

      {/* Version list */}
      <div className="space-y-2 mb-4 max-h-64 overflow-y-auto">
        {versions.map((v) => (
          <div key={v._id} className="border rounded p-2 text-xs">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="font-medium">v{v.version}</span>
                <span className={`px-1.5 py-0.5 rounded ${triggerColor(v.trigger)}`}>
                  {triggerLabel(v.trigger)}
                </span>
              </div>
              <button
                onClick={() => handleRollback(v.version)}
                disabled={rolling || v.version === versions[0]?.version}
                className="text-blue-600 hover:underline disabled:opacity-30 disabled:no-underline"
              >
                Rollback
              </button>
            </div>
            {v.note ? (
              <p className="text-gray-600 mt-1">{v.note}</p>
            ) : (
              editingNote === v.version ? (
                <div className="mt-1 flex gap-1">
                  <input
                    type="text"
                    value={noteText}
                    onChange={(e) => setNoteText(e.target.value)}
                    className="border rounded px-1.5 py-0.5 text-xs flex-1"
                    placeholder="Add note..."
                    autoFocus
                  />
                  <button
                    onClick={() => handleSaveNote(v.version)}
                    className="text-blue-600"
                  >
                    Save
                  </button>
                  <button
                    onClick={() => setEditingNote(null)}
                    className="text-gray-400"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => { setEditingNote(v.version); setNoteText(""); }}
                  className="text-gray-400 hover:text-gray-600 mt-1"
                >
                  + Add note
                </button>
              )
            )}
            <p className="text-gray-400 mt-1">
              {v.created_at ? new Date(v.created_at).toLocaleString() : ""}
            </p>
          </div>
        ))}
      </div>

      {/* Diff comparison */}
      {versions.length >= 2 && (
        <div className="border-t pt-3">
          <h4 className="text-xs font-medium text-gray-500 mb-2">Compare Versions</h4>
          <div className="flex gap-2 items-center mb-2">
            <select
              value={selectedV1 ?? ""}
              onChange={(e) => setSelectedV1(Number(e.target.value))}
              className="border rounded px-2 py-1 text-xs"
            >
              <option value="">v--</option>
              {versions.map((v) => (
                <option key={v.version} value={v.version}>v{v.version}</option>
              ))}
            </select>
            <span className="text-xs text-gray-400">vs</span>
            <select
              value={selectedV2 ?? ""}
              onChange={(e) => setSelectedV2(Number(e.target.value))}
              className="border rounded px-2 py-1 text-xs"
            >
              <option value="">v--</option>
              {versions.map((v) => (
                <option key={v.version} value={v.version}>v{v.version}</option>
              ))}
            </select>
            <button
              onClick={handleCompare}
              disabled={selectedV1 === null || selectedV2 === null || selectedV1 === selectedV2}
              className="px-2 py-1 bg-gray-800 text-white rounded text-xs disabled:opacity-30"
            >
              Diff
            </button>
          </div>

          {diff && (
            <div className="bg-gray-50 rounded p-2 text-xs max-h-48 overflow-y-auto">
              {diff.changed_fields.length === 0 ? (
                <p className="text-gray-500">No differences found.</p>
              ) : (
                <div className="space-y-1">
                  <p className="font-medium text-gray-700">
                    Changed: {diff.changed_fields.join(", ")}
                  </p>
                  {diff.changed_fields.map((field) => (
                    <details key={field} className="border-l-2 border-blue-300 pl-2">
                      <summary className="cursor-pointer text-blue-700 font-medium">{field}</summary>
                      <div className="mt-1 grid grid-cols-2 gap-1">
                        <div className="bg-red-50 rounded p-1">
                          <span className="text-red-500 font-medium">v{selectedV1}</span>
                          <pre className="whitespace-pre-wrap text-gray-600 mt-0.5">
                            {JSON.stringify(diff.diff[field]?.v1, null, 1)?.slice(0, 300)}
                          </pre>
                        </div>
                        <div className="bg-green-50 rounded p-1">
                          <span className="text-green-500 font-medium">v{selectedV2}</span>
                          <pre className="whitespace-pre-wrap text-gray-600 mt-0.5">
                            {JSON.stringify(diff.diff[field]?.v2, null, 1)?.slice(0, 300)}
                          </pre>
                        </div>
                      </div>
                    </details>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
