"use client";

import { useState, useEffect } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface PipelineMetrics {
  pipeline_count: number;
  avg_duration_s: number;
  max_duration_s: number;
  avg_llm_calls: number;
  avg_search_calls: number;
  resource_agent_trigger_rate: number;
  stage_durations: Record<string, { avg_duration_s: number; trigger_count: number }>;
}

interface CacheStats {
  cached_research_entries: number;
  ttl_days: number;
}

interface FeedbackStats {
  total_feedback: number;
  rerun_triggered_count: number;
  rerun_trigger_rate: number;
  with_approved_directions: number;
  with_rejected_directions: number;
  target_distribution: Record<string, number>;
}

interface BriefStats {
  total_versions: number;
  trigger_distribution: Record<string, number>;
  rerun_count: number;
  rollback_count: number;
}

export default function AnalyticsPage() {
  const [pipeline, setPipeline] = useState<PipelineMetrics | null>(null);
  const [cache, setCache] = useState<CacheStats | null>(null);
  const [feedback, setFeedback] = useState<FeedbackStats | null>(null);
  const [brief, setBrief] = useState<BriefStats | null>(null);
  const [loading, setLoading] = useState(true);

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers = { Authorization: `Bearer ${token}` };

  useEffect(() => {
    Promise.all([
      fetch(`${API_BASE}/api/v1/analytics/pipeline-metrics`, { headers }).then((r) => r.json()),
      fetch(`${API_BASE}/api/v1/analytics/cache-stats`, { headers }).then((r) => r.json()),
      fetch(`${API_BASE}/api/v1/analytics/feedback-stats`, { headers }).then((r) => r.json()),
      fetch(`${API_BASE}/api/v1/analytics/brief-stats`, { headers }).then((r) => r.json()),
    ]).then(([p, c, f, b]) => {
      setPipeline(p);
      setCache(c);
      setFeedback(f);
      setBrief(b);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return <div className="p-8 text-center text-gray-500">Loading analytics...</div>;
  }

  return (
    <div className="max-w-6xl mx-auto p-8">
      <h1 className="text-2xl font-bold mb-8">Analytics Dashboard</h1>

      {/* Top-level KPIs */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        <StatCard label="Total Pipelines" value={pipeline?.pipeline_count ?? 0} />
        <StatCard
          label="Avg Duration"
          value={`${pipeline?.avg_duration_s ?? 0}s`}
          sub={`Max: ${pipeline?.max_duration_s ?? 0}s`}
        />
        <StatCard
          label="Avg LLM Calls"
          value={pipeline?.avg_llm_calls ?? 0}
          sub="Budget: 30 max"
        />
        <StatCard
          label="Resource Trigger Rate"
          value={`${pipeline?.resource_agent_trigger_rate ?? 0}%`}
          sub="of all pipelines"
        />
      </div>

      <div className="grid grid-cols-2 gap-6 mb-8">
        {/* Stage Durations */}
        <section className="border rounded p-4">
          <h2 className="font-semibold text-sm mb-3">Stage Performance</h2>
          {pipeline?.stage_durations && Object.keys(pipeline.stage_durations).length > 0 ? (
            <div className="space-y-2">
              {Object.entries(pipeline.stage_durations).map(([stage, data]) => (
                <div key={stage} className="flex items-center gap-3">
                  <span className="text-xs text-gray-600 w-32 truncate">{stage}</span>
                  <div className="flex-1 bg-gray-100 rounded-full h-4 relative">
                    <div
                      className="bg-blue-500 h-4 rounded-full"
                      style={{ width: `${Math.min((data.avg_duration_s / (pipeline.avg_duration_s || 1)) * 100, 100)}%` }}
                    />
                  </div>
                  <span className="text-xs text-gray-500 w-16 text-right">{data.avg_duration_s}s</span>
                  <span className="text-xs text-gray-400 w-10 text-right">x{data.trigger_count}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-gray-500">No stage data yet.</p>
          )}
        </section>

        {/* Feedback Stats */}
        <section className="border rounded p-4">
          <h2 className="font-semibold text-sm mb-3">Client Feedback</h2>
          {feedback && feedback.total_feedback > 0 ? (
            <div className="space-y-3">
              <div className="grid grid-cols-3 gap-2 text-center">
                <MiniStat label="Total" value={feedback.total_feedback} />
                <MiniStat label="Triggered Rerun" value={`${feedback.rerun_trigger_rate}%`} />
                <MiniStat label="Approved Dirs" value={feedback.with_approved_directions} />
              </div>
              {Object.keys(feedback.target_distribution).length > 0 && (
                <div>
                  <p className="text-xs text-gray-500 mb-1">By Target:</p>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(feedback.target_distribution).map(([target, count]) => (
                      <span key={target} className="text-xs bg-gray-100 rounded px-2 py-0.5">
                        {target}: {count}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <p className="text-xs text-gray-500">No feedback data yet.</p>
          )}
        </section>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Cache Stats */}
        <section className="border rounded p-4">
          <h2 className="font-semibold text-sm mb-3">Research Cache</h2>
          <div className="grid grid-cols-2 gap-2 text-center">
            <MiniStat label="Cached Entries" value={cache?.cached_research_entries ?? 0} />
            <MiniStat label="TTL" value={`${cache?.ttl_days ?? 30} days`} />
          </div>
        </section>

        {/* Version Stats */}
        <section className="border rounded p-4">
          <h2 className="font-semibold text-sm mb-3">Version History</h2>
          {brief && brief.total_versions > 0 ? (
            <div className="space-y-2">
              <div className="grid grid-cols-3 gap-2 text-center">
                <MiniStat label="Versions" value={brief.total_versions} />
                <MiniStat label="Reruns" value={brief.rerun_count} />
                <MiniStat label="Rollbacks" value={brief.rollback_count} />
              </div>
              {Object.keys(brief.trigger_distribution).length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {Object.entries(brief.trigger_distribution).map(([trigger, count]) => (
                    <span key={trigger} className="text-xs bg-gray-100 rounded px-2 py-0.5">
                      {trigger}: {count}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <p className="text-xs text-gray-500">No version data yet.</p>
          )}
        </section>
      </div>
    </div>
  );
}

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="border rounded p-4 text-center">
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-xs text-gray-500 mt-1">{label}</p>
      {sub && <p className="text-xs text-gray-400">{sub}</p>}
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <p className="text-lg font-semibold">{value}</p>
      <p className="text-xs text-gray-500">{label}</p>
    </div>
  );
}
