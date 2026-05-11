"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useDispatch, useSelector } from "react-redux";

import type { AppDispatch, RootState } from "@/store/store";
import { fetchRecords, setTab, setClientFilter } from "@/store/campaignsSlice";

const confidenceBadge = (c: string) => {
  const colors: Record<string, string> = {
    high: "bg-green-100 text-green-700",
    partial: "bg-yellow-100 text-yellow-700",
    low: "bg-red-100 text-red-700",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded ${colors[c] || "bg-gray-100 text-gray-700"}`}>
      {c}
    </span>
  );
};

const statusBadge = (s: string) => {
  const isPending = s === "pending_confirmation";
  return (
    <span className={`text-xs px-2 py-0.5 rounded ${isPending ? "bg-orange-100 text-orange-700" : "bg-green-100 text-green-700"}`}>
      {isPending ? "Pending" : "Confirmed"}
    </span>
  );
};

export default function CampaignsPage() {
  const dispatch = useDispatch<AppDispatch>();
  const { records, loading, tab, clientFilter } = useSelector(
    (state: RootState) => state.campaigns
  );

  useEffect(() => {
    dispatch(fetchRecords({ tab, clientId: clientFilter || undefined }));
  }, [dispatch, tab, clientFilter]);

  return (
    <div className="max-w-5xl mx-auto p-8">
      <h1 className="text-2xl font-bold mb-6">Campaign Knowledge Base</h1>

      <div className="flex gap-3 mb-6 items-center">
        <button
          onClick={() => dispatch(setTab("pending"))}
          className={`px-4 py-2 rounded text-sm ${tab === "pending" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-700"}`}
        >
          Pending Review
        </button>
        <button
          onClick={() => dispatch(setTab("all"))}
          className={`px-4 py-2 rounded text-sm ${tab === "all" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-700"}`}
        >
          All Records
        </button>
        <input
          type="text"
          value={clientFilter}
          onChange={(e) => dispatch(setClientFilter(e.target.value))}
          placeholder="Filter by Client ID"
          className="border rounded px-3 py-2 text-sm w-48 ml-auto"
        />
      </div>

      {loading && <p className="text-gray-500 text-sm">Loading...</p>}

      {!loading && records.length === 0 && (
        <p className="text-gray-500 text-sm">
          {tab === "pending" ? "No records pending review." : "No campaign records found."}
        </p>
      )}

      {!loading && records.length > 0 && (
        <div className="space-y-3">
          {records.map((r) => (
            <Link
              key={r.id}
              href={`/campaigns/${r.id}`}
              className="block border rounded p-4 hover:border-blue-300 hover:shadow-sm transition"
            >
              <div className="flex items-center gap-3 mb-2">
                {statusBadge(r.status)}
                {confidenceBadge(r.confidence)}
                {r.meta?.campaign_type && (
                  <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded">
                    {r.meta.campaign_type}
                  </span>
                )}
                {r.meta?.industry && (
                  <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                    {r.meta.industry}
                  </span>
                )}
                {r.meta?.budget_tier && (
                  <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                    {r.meta.budget_tier}
                  </span>
                )}
              </div>
              <div className="text-sm font-medium text-gray-800">
                {r.strategy_decisions?.big_idea as string || "No big idea extracted"}
              </div>
              <div className="text-xs text-gray-500 mt-1 flex gap-4">
                {r.meta?.target_audience_summary && <span>{r.meta.target_audience_summary}</span>}
                {r.client_id && <span>Client: {r.client_id}</span>}
                {r.created_at && <span>Created: {new Date(r.created_at).toLocaleDateString()}</span>}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
