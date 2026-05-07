"use client";

import { useState } from "react";

interface Props {
  onSubmit: (brief: string, clientId: string, projectId: string) => void;
}

export function BriefInput({ onSubmit }: Props) {
  const [brief, setBrief] = useState("");
  const [clientId, setClientId] = useState("");
  const [projectId, setProjectId] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!brief.trim() || !clientId.trim()) return;
    onSubmit(brief, clientId, projectId);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Client ID
        </label>
        <input
          type="text"
          value={clientId}
          onChange={(e) => setClientId(e.target.value)}
          className="w-full border rounded px-3 py-2 text-sm"
          placeholder="Enter client ID"
          required
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Project ID
        </label>
        <input
          type="text"
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
          className="w-full border rounded px-3 py-2 text-sm"
          placeholder="Enter project ID (optional)"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Brief
        </label>
        <textarea
          value={brief}
          onChange={(e) => setBrief(e.target.value)}
          rows={10}
          className="w-full border rounded px-3 py-2 text-sm"
          placeholder="Paste your client brief here... (supports Chinese and English)"
          required
        />
      </div>

      <button
        type="submit"
        className="w-full py-2 bg-blue-600 text-white rounded font-medium hover:bg-blue-700 transition-colors"
      >
        Start Pipeline
      </button>
    </form>
  );
}
