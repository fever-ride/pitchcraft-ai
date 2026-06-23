"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";

type FeedbackTarget = "strategy" | "structure" | "slide" | "resource" | "overall";

interface FeedbackPanelProps {
  proposalId: string;
  defaultTarget?: FeedbackTarget;
  onSubmitted?: () => void;
  onRerunTriggered?: () => void;
}

export default function FeedbackPanel({
  proposalId,
  defaultTarget = "overall",
  onSubmitted,
  onRerunTriggered,
}: FeedbackPanelProps) {
  const [target, setTarget] = useState<FeedbackTarget>(defaultTarget);
  const [content, setContent] = useState("");
  const [approvedInput, setApprovedInput] = useState("");
  const [rejectedInput, setRejectedInput] = useState("");
  const [approved, setApproved] = useState<string[]>([]);
  const [rejected, setRejected] = useState<string[]>([]);
  const [triggerRerun, setTriggerRerun] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ suggested_rerun_node?: string; rerun_triggered?: boolean } | null>(null);

  const addDirection = (type: "approved" | "rejected") => {
    if (type === "approved" && approvedInput.trim()) {
      setApproved([...approved, approvedInput.trim()]);
      setApprovedInput("");
    } else if (type === "rejected" && rejectedInput.trim()) {
      setRejected([...rejected, rejectedInput.trim()]);
      setRejectedInput("");
    }
  };

  const handleSubmit = async () => {
    if (!content.trim()) return;
    setSubmitting(true);

    const res = await apiFetch(`/api/v1/proposals/${proposalId}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        target,
        content,
        approved_directions: approved,
        rejected_directions: rejected,
        trigger_rerun: triggerRerun,
      }),
    });

    const data = await res.json();
    setResult(data);
    setSubmitting(false);
    onSubmitted?.();
    if (data.rerun_triggered) {
      onRerunTriggered?.();
    }
  };

  return (
    <div className="border rounded-lg p-4 bg-white">
      <h3 className="font-semibold text-sm mb-3">Feedback</h3>

      <div className="mb-3">
        <label className="text-xs text-gray-500 block mb-1">Target</label>
        <select
          value={target}
          onChange={(e) => setTarget(e.target.value as FeedbackTarget)}
          className="w-full border rounded px-2 py-1.5 text-sm"
        >
          <option value="overall">Overall</option>
          <option value="strategy">Strategy</option>
          <option value="structure">Deck Structure</option>
          <option value="slide">Slide Content</option>
          <option value="resource">Resources</option>
        </select>
      </div>

      <div className="mb-3">
        <label className="text-xs text-gray-500 block mb-1">Comments</label>
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          className="w-full border rounded px-2 py-1.5 text-sm h-20 resize-none"
          placeholder="What should be changed or improved?"
        />
      </div>

      <div className="mb-3">
        <label className="text-xs text-gray-500 block mb-1">Approved Directions</label>
        <div className="flex gap-1 mb-1">
          <input
            value={approvedInput}
            onChange={(e) => setApprovedInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addDirection("approved"))}
            className="flex-1 border rounded px-2 py-1 text-sm"
            placeholder="Direction to keep"
          />
          <button onClick={() => addDirection("approved")} className="px-2 py-1 text-xs bg-green-100 text-green-700 rounded">+</button>
        </div>
        {approved.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {approved.map((d, i) => (
              <span key={i} className="text-xs bg-green-50 text-green-700 px-2 py-0.5 rounded">
                {d}
                <button onClick={() => setApproved(approved.filter((_, j) => j !== i))} className="ml-1">&times;</button>
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="mb-3">
        <label className="text-xs text-gray-500 block mb-1">Rejected Directions</label>
        <div className="flex gap-1 mb-1">
          <input
            value={rejectedInput}
            onChange={(e) => setRejectedInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addDirection("rejected"))}
            className="flex-1 border rounded px-2 py-1 text-sm"
            placeholder="Direction to avoid"
          />
          <button onClick={() => addDirection("rejected")} className="px-2 py-1 text-xs bg-red-100 text-red-700 rounded">+</button>
        </div>
        {rejected.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {rejected.map((d, i) => (
              <span key={i} className="text-xs bg-red-50 text-red-700 px-2 py-0.5 rounded">
                {d}
                <button onClick={() => setRejected(rejected.filter((_, j) => j !== i))} className="ml-1">&times;</button>
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="mb-4 flex items-center gap-2">
        <input
          type="checkbox"
          id="rerun"
          checked={triggerRerun}
          onChange={(e) => setTriggerRerun(e.target.checked)}
          className="rounded"
        />
        <label htmlFor="rerun" className="text-sm text-gray-700">Trigger rerun from suggested node</label>
      </div>

      <button
        onClick={handleSubmit}
        disabled={submitting || !content.trim()}
        className="w-full py-2 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
      >
        {submitting ? "Submitting..." : "Submit Feedback"}
      </button>

      {result && (
        <div className="mt-3 text-xs text-gray-600 bg-gray-50 rounded p-2">
          <p>Suggested rerun node: <span className="font-medium">{result.suggested_rerun_node || "—"}</span></p>
          {result.rerun_triggered && <p className="text-green-600 mt-1">Rerun triggered!</p>}
        </div>
      )}
    </div>
  );
}
