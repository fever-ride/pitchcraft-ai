"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import FeedbackPanel from "@/components/feedback/FeedbackPanel";
import VersionPanel from "@/components/versions/VersionPanel";
import { useTranslations } from "next-intl";
import { apiFetch } from "@/lib/api";

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

interface Proposal {
  proposal_id: string;
  structured_brief: Record<string, unknown> | null;
  strategy_result: Record<string, unknown> | null;
  slides: unknown[] | null;
  pptx_path: string | null;
}

export default function ProposalPage() {
  const t = useTranslations("proposals");
  const { proposalId } = useParams<{ proposalId: string }>();
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [loading, setLoading] = useState(true);
  const [rerunStatus, setRerunStatus] = useState<"idle" | "running" | "completed">("idle");
  const [rerunNode, setRerunNode] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const loadProposal = () => {
    apiFetch(`/api/v1/proposals/${proposalId}`)
      .then((r) => r.json())
      .then((data) => {
        setProposal(data);
        setLoading(false);
      });
  };

  // Connect WebSocket to track rerun progress for this proposal.
  // The rerun uses the same pipeline_id (= proposal_id), so events arrive
  // on the same channel. Only open the socket when a rerun is triggered.
  const connectRerunSocket = () => {
    if (wsRef.current) wsRef.current.close();

    const ws = new WebSocket(`${WS_BASE}/ws/pipeline/${proposalId}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.event === "node_entered") {
        setRerunNode(data.node);
      } else if (
        data.event === "pipeline_complete" ||
        data.event === "pipeline_completed"
      ) {
        setRerunStatus("completed");
        setRerunNode(null);
        ws.close();
        loadProposal();
      }
    };

    ws.onerror = () => {
      setRerunStatus("idle");
      ws.close();
    };
  };

  const handleRerunTriggered = () => {
    setRerunStatus("running");
    setRerunNode(null);
    connectRerunSocket();
  };

  useEffect(() => {
    loadProposal();
    return () => wsRef.current?.close();
  }, [proposalId]);

  if (loading) {
    return <div className="p-8 text-center text-gray-500">{t("loading")}</div>;
  }

  if (!proposal) {
    return <div className="p-8 text-center text-red-500">{t("notFound")}</div>;
  }

  return (
    <div className="max-w-5xl mx-auto p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">{t("title")}</h1>
        {proposal.pptx_path && (
          <button
            onClick={() => {
              const token = localStorage.getItem("token");
              window.open(
                `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/proposals/${proposalId}/download?token=${token}`,
                "_blank"
              );
            }}
            className="px-4 py-2 bg-blue-600 text-white rounded font-medium hover:bg-blue-700"
          >
            {t("downloadPPT")}
          </button>
        )}
      </div>

      {rerunStatus === "running" && (
        <div className="mb-6 px-4 py-3 bg-blue-50 border border-blue-200 rounded text-sm text-blue-700 flex items-center gap-2">
          <span className="animate-spin inline-block w-3 h-3 border-2 border-blue-500 border-t-transparent rounded-full" />
          {rerunNode ? t("rerunningNode", { node: rerunNode }) : t("rerunning")}
        </div>
      )}

      {rerunStatus === "completed" && (
        <div className="mb-6 px-4 py-3 bg-green-50 border border-green-200 rounded text-sm text-green-700">
          {t("rerunComplete")}
        </div>
      )}

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 space-y-6">
          {proposal.structured_brief && (
            <section>
              <h2 className="text-lg font-semibold mb-3">{t("brief")}</h2>
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
              <h2 className="text-lg font-semibold mb-3">{t("strategy")}</h2>
              <div className="bg-gray-50 rounded p-4 text-sm">
                {typeof proposal.strategy_result === "object" && (
                  <div className="space-y-2">
                    {!!(proposal.strategy_result as Record<string, unknown>).big_idea && (
                      <div>
                        <span className="font-medium text-gray-500">{t("bigIdea")}</span>
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
                {t("slides", { count: proposal.slides.length })}
              </h2>
              <div className="space-y-2">
                {proposal.slides.map((slide: any, i: number) => (
                  <div key={i} className="border rounded p-3">
                    <h4 className="font-medium text-sm">
                      {slide.content?.title || t("slide", { num: i + 1 })}
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
            <FeedbackPanel
              proposalId={proposalId}
              onSubmitted={loadProposal}
              onRerunTriggered={handleRerunTriggered}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
