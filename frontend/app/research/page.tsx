"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Competitor {
  name: string;
  positioning: string;
  recent_activity: string;
  social_presence?: {
    platforms: string[];
    content_style: string;
    engagement_level: string;
    notable_campaigns: string[];
  };
}

interface ResearchResult {
  competitors: Competitor[];
  market_trends: string[];
  content_trends?: { trend: string; platforms: string[]; relevance: string }[];
  opportunities: string[];
  risks?: string[];
  recommended_approach?: string;
  from_cache?: boolean;
  social_data_source?: string;
  fetched_at?: number;
}

export default function ResearchPage() {
  const [pipelineId, setPipelineId] = useState("");
  const [data, setData] = useState<ResearchResult | null>(null);
  const [loading, setLoading] = useState(false);

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;

  const loadResearch = async () => {
    if (!pipelineId) return;
    setLoading(true);
    const res = await fetch(`${API_BASE}/api/v1/pipeline/${pipelineId}/strategy`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const json = await res.json();
    setData(json.research_result || null);
    setLoading(false);
  };

  const handleRefresh = async () => {
    if (!pipelineId) return;
    setLoading(true);
    await fetch(`${API_BASE}/api/v1/pipeline/${pipelineId}/rerun`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ rerun_from: "parallel_research_strategy", refresh_research: true }),
    });
    setLoading(false);
    setTimeout(loadResearch, 3000);
  };

  return (
    <div className="max-w-5xl mx-auto p-8">
      <h1 className="text-2xl font-bold mb-6">Research Data</h1>

      <div className="flex gap-3 mb-6">
        <input
          type="text"
          value={pipelineId}
          onChange={(e) => setPipelineId(e.target.value)}
          placeholder="Pipeline ID"
          className="border rounded px-3 py-2 text-sm w-72"
        />
        <button
          onClick={loadResearch}
          disabled={loading || !pipelineId}
          className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Loading..." : "Load"}
        </button>
        {data && (
          <button
            onClick={handleRefresh}
            disabled={loading}
            className="px-4 py-2 border border-blue-600 text-blue-600 rounded text-sm hover:bg-blue-50 disabled:opacity-50"
          >
            Refresh Research
          </button>
        )}
      </div>

      {data && (
        <div className="space-y-6">
          {/* Meta */}
          <div className="flex gap-4 text-xs text-gray-500">
            {data.from_cache && <span className="bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded">From Cache</span>}
            {data.social_data_source && <span>Source: {data.social_data_source}</span>}
            {data.fetched_at && <span>Fetched: {new Date(data.fetched_at * 1000).toLocaleString()}</span>}
          </div>

          {/* Recommended Approach */}
          {data.recommended_approach && (
            <div className="bg-blue-50 border border-blue-200 rounded p-4">
              <h3 className="font-medium text-sm text-blue-800 mb-1">Recommended Approach</h3>
              <p className="text-sm text-blue-700">{data.recommended_approach}</p>
            </div>
          )}

          {/* Competitors */}
          <section>
            <h2 className="text-lg font-semibold mb-3">Competitors ({data.competitors.length})</h2>
            <div className="space-y-3">
              {data.competitors.map((c, i) => (
                <div key={i} className="border rounded p-3">
                  <div className="font-medium text-sm">{c.name}</div>
                  <div className="text-xs text-gray-600 mt-1">
                    <p><strong>Positioning:</strong> {c.positioning}</p>
                    <p><strong>Recent:</strong> {c.recent_activity}</p>
                  </div>
                  {c.social_presence && (
                    <div className="mt-2 text-xs text-gray-500 bg-gray-50 rounded p-2">
                      <p>Platforms: {c.social_presence.platforms.join(", ")}</p>
                      <p>Content style: {c.social_presence.content_style}</p>
                      <p>Engagement: {c.social_presence.engagement_level}</p>
                      {c.social_presence.notable_campaigns.length > 0 && (
                        <p>Campaigns: {c.social_presence.notable_campaigns.join(", ")}</p>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>

          {/* Market Trends */}
          <section>
            <h2 className="text-lg font-semibold mb-3">Market Trends</h2>
            <ul className="list-disc pl-5 text-sm space-y-1">
              {data.market_trends.map((t, i) => <li key={i}>{t}</li>)}
            </ul>
          </section>

          {/* Content Trends */}
          {data.content_trends && data.content_trends.length > 0 && (
            <section>
              <h2 className="text-lg font-semibold mb-3">Content Trends</h2>
              <div className="space-y-2">
                {data.content_trends.map((ct, i) => (
                  <div key={i} className="border rounded p-2 text-sm">
                    <strong>{ct.trend}</strong>
                    <span className="text-gray-500 ml-2">({ct.platforms.join(", ")})</span>
                    <p className="text-xs text-gray-600 mt-0.5">{ct.relevance}</p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Opportunities + Risks */}
          <div className="grid grid-cols-2 gap-4">
            <section>
              <h2 className="text-lg font-semibold mb-3">Opportunities</h2>
              <ul className="list-disc pl-5 text-sm space-y-1">
                {data.opportunities.map((o, i) => <li key={i}>{o}</li>)}
              </ul>
            </section>
            {data.risks && data.risks.length > 0 && (
              <section>
                <h2 className="text-lg font-semibold mb-3">Risks</h2>
                <ul className="list-disc pl-5 text-sm space-y-1 text-red-700">
                  {data.risks.map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              </section>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
