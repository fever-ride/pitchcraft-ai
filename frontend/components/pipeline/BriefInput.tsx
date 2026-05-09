"use client";

import { useState } from "react";

interface Props {
  onSubmit: (brief: string, clientId: string, projectId: string, outputLanguage: string) => void;
}

export function BriefInput({ onSubmit }: Props) {
  const [brief, setBrief] = useState("");
  const [clientId, setClientId] = useState("");
  const [projectId, setProjectId] = useState("");
  const [outputLanguage, setOutputLanguage] = useState("auto");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!brief.trim() || !clientId.trim()) return;
    onSubmit(brief, clientId, projectId, outputLanguage);
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
          Output Language
        </label>
        <select
          value={outputLanguage}
          onChange={(e) => setOutputLanguage(e.target.value)}
          className="w-full border rounded px-3 py-2 text-sm"
        >
          <option value="auto">Auto (same as brief language)</option>
          <option value="en">English</option>
          <option value="zh">中文</option>
        </select>
        <p className="text-xs text-gray-400 mt-1">
          Controls the language of the final deck. Brief understanding always uses the brief&apos;s own language.
        </p>
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
