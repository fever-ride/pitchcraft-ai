"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import FeedbackPanel from "@/components/feedback/FeedbackPanel";
import VersionPanel from "@/components/versions/VersionPanel";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Proposal {
  proposal_id: string;
  structured_brief: Record<string, unknown> | null;
  strategy_result: Record<string, unknown> | null;
  slides: unknown[] | null;
  pptx_path: string | null;
}

export default function ProposalPage() {
  const { proposalId } = useParams<{ proposalId: string }>();
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [loading, setLoading] = useState(true);

  const loadProposal = () => {
    fetch(`${API_BASE}/api/v1/proposals/${proposalId}`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
    })
      .then((r) => r.json())
      .then((data) => {
        setProposal(data);
        setLoading(false);
      });
  };

  useEffect(() => {
    loadProposal();
  }, [proposalId]);

  const handleDownload = () => {
    const token = localStorage.getItem("token");
    window.open(
      `${API_BASE}/api/v1/proposals/${proposalId}/download?token=${token}`,
      "_blank"
    );
  };

  if (loading) {
    return <div className="p-8 text-center text-gray-500">Loading proposal...</div>;
  }

  if (!proposal) {
    return <div className="p-8 text-center text-red-500">Proposal not found</div>;
  }

  return (
    <div className="max-w-5xl mx-auto p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Proposal</h1>
        {proposal.pptx_path && (
          <button
            onClick={handleDownload}
            className="px-4 py-2 bg-blue-600 text-white rounded font-medium hover:bg-blue-700"
          >
            Download PPT
          </button>
        )}
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 space-y-6">
          {proposal.structured_brief && (
            <section>
              <h2 className="text-lg font-semibold mb-3">Brief</h2>
              <div className="bg-gray-50 rounded p-4 text-sm">
                {Object.entries(proposal.structured_brief).map(([key, value]) => (
                  <div key={key} className="flex gap-2 mb-1">
                    <span className="font-medium text-gray-500 w-28">{key}:</span>
                    <span className="text-gray-800">
                      {Array.isArray(value) ? value.join(", ") : String(value || "—")}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          )}

          {proposal.strategy_result && (
            <section>
              <h2 className="text-lg font-semibold mb-3">Strategy</h2>
              <div className="bg-gray-50 rounded p-4 text-sm">
                {typeof proposal.strategy_result === "object" && (
                  <div className="space-y-2">
                    {(proposal.strategy_result as Record<string, unknown>).big_idea && (
                      <div>
                        <span className="font-medium text-gray-500">Big Idea: </span>
                        <span>{String((proposal.strategy_result as Record<string, unknown>).big_idea)}</span>
                      </div>
                    )}
                    <pre className="text-xs text-gray-600 whitespace-pre-wrap">
                      {JSON.stringify(proposal.strategy_result, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            </section>
          )}

          {proposal.slides && proposal.slides.length > 0 && (
            <section>
              <h2 className="text-lg font-semibold mb-3">
                Slides ({proposal.slides.length})
              </h2>
              <div className="space-y-2">
                {proposal.slides.map((slide: any, i: number) => (
                  <div key={i} className="border rounded p-3">
                    <h4 className="font-medium text-sm">
                      {slide.content?.title || `Slide ${i + 1}`}
                    </h4>
                    {slide.content?.body && (
                      <p className="text-xs text-gray-600 mt-1">{slide.content.body}</p>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>

        <div className="col-span-1">
          <div className="sticky top-8 space-y-4">
            <VersionPanel proposalId={proposalId} onRollback={loadProposal} />
            <FeedbackPanel proposalId={proposalId} onSubmitted={loadProposal} />
          </div>
        </div>
      </div>
    </div>
  );
}
