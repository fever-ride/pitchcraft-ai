"use client";

import Link from "next/link";
import { useEffect, useRef, useState, useCallback } from "react";
import { useDispatch, useSelector } from "react-redux";
import { useTranslations } from "next-intl";

import type { AppDispatch, RootState } from "@/store/store";
import { fetchRecords, setTab } from "@/store/campaignsSlice";
import { apiFetch } from "@/lib/api";

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

// ── Types ──────────────────────────────────────────────────────────────────────

interface Client {
  _id: string;
  name: string;
  industry: string | null;
}

interface ProcessingArchive {
  archive_id: string;
  filename: string;
  client_id: string;
  status?: "pending" | "processing" | "failed";
  processing_error?: string;
}

// ── Badge helpers (components so they can use hooks) ───────────────────────────

function ConfidenceBadge({ value }: { value: string }) {
  const t = useTranslations("enums");
  const colors: Record<string, string> = {
    high: "bg-green-100 text-green-700",
    partial: "bg-yellow-100 text-yellow-700",
    low: "bg-red-100 text-red-700",
  };
  const label = (() => {
    try { return t(`confidence.${value}` as Parameters<typeof t>[0]); } catch { return value; }
  })();
  return (
    <span className={`text-xs px-2 py-0.5 rounded ${colors[value] || "bg-gray-100 text-gray-700"}`}>
      {label}
    </span>
  );
}

function StatusBadge({ value }: { value: string }) {
  const t = useTranslations("enums");
  const isPending = value === "pending_confirmation";
  const label = (() => {
    try { return t(`confirmationStatus.${value}` as Parameters<typeof t>[0]); } catch { return value; }
  })();
  return (
    <span className={`text-xs px-2 py-0.5 rounded ${isPending ? "bg-orange-100 text-orange-700" : "bg-green-100 text-green-700"}`}>
      {label}
    </span>
  );
}

function CampaignTypeBadge({ value }: { value: string }) {
  const t = useTranslations("enums");
  const label = (() => {
    try { return t(`campaignType.${value}` as Parameters<typeof t>[0]); } catch { return value.replace(/_/g, " "); }
  })();
  return (
    <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded">{label}</span>
  );
}

function BudgetTierBadge({ value }: { value: string }) {
  const t = useTranslations("enums");
  const label = (() => {
    try { return t(`budgetTier.${value}` as Parameters<typeof t>[0]); } catch { return value.replace(/_/g, " "); }
  })();
  return (
    <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">{label}</span>
  );
}

// ── Processing banner — shown per in-flight archive ───────────────────────────

function ProcessingBanner({
  archives,
  onDismissError,
}: {
  archives: ProcessingArchive[];
  onDismissError: (archiveId: string) => void;
}) {
  const t = useTranslations("campaigns");
  if (archives.length === 0) return null;
  return (
    <div className="mb-4 space-y-2">
      {archives.map((a) => {
        const failed = a.status === "failed";
        return (
          <div
            key={a.archive_id}
            className={`flex items-start gap-2 text-sm rounded px-3 py-2 border ${
              failed
                ? "text-red-700 bg-red-50 border-red-200"
                : "text-blue-700 bg-blue-50 border-blue-200"
            }`}
          >
            {failed ? (
              <svg className="w-4 h-4 shrink-0 mt-0.5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
            ) : (
              <svg className="animate-spin w-4 h-4 shrink-0 mt-0.5" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
              </svg>
            )}
            <div className="flex-1 min-w-0">
              <span className="font-medium">{a.filename}</span>
              {failed ? (
                <p className="mt-0.5 text-red-600 text-xs">{a.processing_error}</p>
              ) : (
                <span className="ml-1 text-blue-500">{t("upload.processingMsg")}</span>
              )}
            </div>
            {failed && (
              <button
                onClick={() => onDismissError(a.archive_id)}
                className="shrink-0 text-red-400 hover:text-red-600 ml-1"
                aria-label="Dismiss"
              >
                ×
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Upload panel ───────────────────────────────────────────────────────────────

function UploadPanel({ onUploaded }: { onUploaded: (archive: ProcessingArchive) => void }) {
  const t = useTranslations("campaigns");
  const tc = useTranslations("common");
  const [clients, setClients] = useState<Client[]>([]);
  const [clientId, setClientId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  // Inline create-client state
  const [showNewClient, setShowNewClient] = useState(false);
  const [newClientName, setNewClientName] = useState("");
  const [newClientIndustry, setNewClientIndustry] = useState("");
  const [creatingClient, setCreatingClient] = useState(false);

  const loadClients = async () => {
    const res = await apiFetch("/api/v1/clients").catch(() => null);
    if (!res?.ok) return;
    const data = await res.json();
    if (Array.isArray(data)) setClients(data);
  };

  useEffect(() => { loadClients(); }, []);

  const handleSelectChange = (value: string) => {
    if (value === "__new__") {
      setShowNewClient(true);
      setClientId("");
    } else {
      setShowNewClient(false);
      setClientId(value);
    }
  };

  const handleCreateClient = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newClientName.trim()) return;
    setCreatingClient(true);
    try {
      const res = await apiFetch("/api/v1/clients", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newClientName.trim(), industry: newClientIndustry.trim() || null }),
      });
      if (!res.ok) throw new Error("Failed to create client");
      const data = await res.json();
      await loadClients();
      setClientId(data.client_id);
      setShowNewClient(false);
      setNewClientName("");
      setNewClientIndustry("");
    } catch {
      // silently ignore — user can retry
    } finally {
      setCreatingClient(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFile(e.target.files?.[0] ?? null);
    setErrorMsg("");
  };

  const handleUpload = async () => {
    if (!clientId || !file) return;
    setUploading(true);
    setErrorMsg("");
    try {
      const form = new FormData();
      form.append("client_id", clientId);
      form.append("file", file);
      const res = await apiFetch("/api/v1/campaigns/upload", {
        method: "POST",
        body: form,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as { detail?: string }).detail ?? `Upload failed (${res.status})`);
      }
      const data = await res.json();
      setFile(null);
      if (fileRef.current) fileRef.current.value = "";
      onUploaded({ archive_id: data.archive_id, filename: file.name, client_id: clientId });
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const selectedClientName = clients.find((c) => c._id === clientId)?.name;

  return (
    <div className="border rounded-xl bg-white p-6 mb-6 shadow-sm">
      {/* Header */}
      <div className="flex items-start gap-4 mb-5">
        <div className="shrink-0 w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-5 h-5 text-blue-600">
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
          </svg>
        </div>
        <div>
          <h2 className="font-semibold text-gray-900">{t("upload.title")}</h2>
          <p className="text-sm text-gray-500 mt-0.5">{t("upload.subtitle")}</p>
        </div>
      </div>

      <div className="flex flex-wrap gap-3 items-end">
        {/* Client picker */}
        <div className="flex-1 min-w-[200px]">
          <label className="block text-xs font-medium text-gray-600 mb-1">
            {t("upload.clientLabel")}
            <span className="ml-1 font-normal text-gray-400">{t("upload.clientHint")}</span>
          </label>
          <select
            value={clientId || (showNewClient ? "__new__" : "")}
            onChange={(e) => handleSelectChange(e.target.value)}
            className="w-full border rounded px-3 py-2 text-sm bg-white"
          >
            <option value="">{t("upload.selectClient")}</option>
            {clients.map((c) => (
              <option key={c._id} value={c._id}>
                {c.name}{c.industry ? ` · ${c.industry}` : ""}
              </option>
            ))}
            <option value="__new__">{t("upload.createNewClient")}</option>
          </select>

          {/* Inline create-client form */}
          {showNewClient && (
            <form onSubmit={handleCreateClient} className="mt-2 border rounded-lg p-3 bg-gray-50 space-y-2">
              <p className="text-xs font-medium text-gray-600">{t("upload.newClientTitle")}</p>
              <input
                type="text"
                value={newClientName}
                onChange={(e) => setNewClientName(e.target.value)}
                placeholder={t("upload.clientNamePlaceholder")}
                className="w-full border rounded px-2 py-1.5 text-sm bg-white"
                required
                autoFocus
              />
              <input
                type="text"
                value={newClientIndustry}
                onChange={(e) => setNewClientIndustry(e.target.value)}
                placeholder={t("upload.industryPlaceholder")}
                className="w-full border rounded px-2 py-1.5 text-sm bg-white"
              />
              <div className="flex gap-2">
                <button
                  type="submit"
                  disabled={creatingClient || !newClientName.trim()}
                  className="px-3 py-1.5 bg-blue-600 text-white rounded text-xs font-medium disabled:opacity-50"
                >
                  {creatingClient ? t("upload.creating") : t("upload.createAndSelect")}
                </button>
                <button
                  type="button"
                  onClick={() => { setShowNewClient(false); setNewClientName(""); setNewClientIndustry(""); }}
                  className="px-3 py-1.5 border rounded text-xs text-gray-600 hover:bg-gray-100"
                >
                  {tc("cancel")}
                </button>
              </div>
            </form>
          )}

          {/* Confirmation pill */}
          {clientId && !showNewClient && (
            <p className="text-xs text-green-600 mt-1">✓ {selectedClientName}</p>
          )}
        </div>

        {/* File picker */}
        <div className="flex-1 min-w-[200px]">
          <label className="block text-xs font-medium text-gray-600 mb-1">{t("upload.fileLabel")}</label>
          <label className={`flex items-center gap-2 border rounded px-3 py-2 text-sm transition-colors ${
            !clientId || showNewClient
              ? "border-gray-200 bg-gray-50 text-gray-300 cursor-not-allowed"
              : file
              ? "border-blue-300 bg-blue-50 text-blue-700 cursor-pointer"
              : "border-gray-300 bg-white text-gray-500 hover:border-gray-400 cursor-pointer"
          }`}>
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 shrink-0">
              <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h6a1 1 0 100-2H7z" clipRule="evenodd" />
            </svg>
            <span className="truncate">{file ? file.name : t("upload.filePlaceholder")}</span>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.docx,.pptx,.ppt"
              onChange={handleFileChange}
              disabled={!clientId || showNewClient}
              className="hidden"
            />
          </label>
        </div>

        {/* Upload button */}
        <button
          onClick={handleUpload}
          disabled={!clientId || !file || uploading || showNewClient}
          className="px-5 py-2 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
        >
          {uploading ? t("upload.uploading") : t("upload.uploadButton")}
        </button>
      </div>

      {errorMsg && (
        <p className="mt-3 text-sm text-red-600">{errorMsg}</p>
      )}
    </div>
  );
}

// ── Decode org_id from JWT (no verification needed — display only) ─────────────

function getOrgIdFromToken(): string | null {
  try {
    const token = localStorage.getItem("token");
    if (!token) return null;
    const payload = JSON.parse(atob(token.split(".")[1]));
    return payload.organization_id ?? payload.org_id ?? null;
  } catch {
    return null;
  }
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function CampaignsPage() {
  const dispatch = useDispatch<AppDispatch>();
  const { records, loading, tab } = useSelector((state: RootState) => state.campaigns);
  const t = useTranslations("campaigns");

  const [clients, setClients] = useState<Client[]>([]);
  const [clientFilter, setClientFilter] = useState("");

  // processingArchives is the source-of-truth list of in-flight uploads.
  // Seeded from GET /archives/processing on mount, updated locally on upload
  // and cleared per-archive when WS push arrives.
  const [processingArchives, setProcessingArchives] = useState<ProcessingArchive[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  // On mount: fetch currently-processing archives to restore banners after refresh
  useEffect(() => {
    apiFetch("/api/v1/campaigns/archives/processing")
      .then((r) => (r.ok ? r.json() : []))
      .then((data: ProcessingArchive[]) => {
        if (Array.isArray(data) && data.length > 0) {
          setProcessingArchives(data);
          dispatch(setTab("pending"));
        }
      })
      .catch(() => {});
  }, [dispatch]);

  // Connect to campaign WS on mount and stay connected.
  // On campaign_record_ready: remove the matching archive from processingArchives,
  // switch to Pending tab, and refresh records.
  useEffect(() => {
    const orgId = getOrgIdFromToken();
    if (!orgId) return;

    const connect = () => {
      const ws = new WebSocket(`${WS_BASE}/ws/campaigns/${orgId}`);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.event === "campaign_record_ready") {
            setProcessingArchives((prev) =>
              prev.filter((a) => a.archive_id !== data.archive_id)
            );
            dispatch(setTab("pending"));
            dispatch(fetchRecords({ tab: "pending", clientId: undefined }));
          } else if (data.event === "campaign_extract_failed") {
            setProcessingArchives((prev) =>
              prev.map((a) =>
                a.archive_id === data.archive_id
                  ? { ...a, status: "failed" as const, processing_error: data.error }
                  : a
              )
            );
          }
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = (event) => {
        if (!event.wasClean) {
          setTimeout(connect, 3000);
        }
      };
    };

    connect();
    return () => {
      wsRef.current?.close();
    };
  }, [dispatch]);

  useEffect(() => {
    apiFetch("/api/v1/clients")
      .then((r) => (r.ok ? r.json() : []))
      .then((data: Client[]) => { if (Array.isArray(data)) setClients(data); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    dispatch(fetchRecords({ tab, clientId: clientFilter || undefined }));
  }, [dispatch, tab, clientFilter]);

  const handleUploaded = useCallback((archive: ProcessingArchive) => {
    setProcessingArchives((prev) => [...prev, { ...archive, status: "processing" as const }]);
    dispatch(setTab("pending"));
  }, [dispatch]);

  const handleDismissError = useCallback((archiveId: string) => {
    setProcessingArchives((prev) => prev.filter((a) => a.archive_id !== archiveId));
  }, []);

  return (
    <div className="max-w-5xl mx-auto p-8">
      <h1 className="text-2xl font-bold mb-1">{t("title")}</h1>
      <p className="text-sm text-gray-500 mb-6">{t("subtitle")}</p>

      <UploadPanel onUploaded={handleUploaded} />

      <ProcessingBanner archives={processingArchives} onDismissError={handleDismissError} />

      {/* Filters + tabs */}
      <div className="flex flex-wrap gap-3 mb-5 items-center">
        <button
          onClick={() => dispatch(setTab("pending"))}
          className={`px-4 py-2 rounded text-sm font-medium transition-colors ${tab === "pending" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-700 hover:bg-gray-200"}`}
        >
          {t("tabs.pending")}
        </button>
        <button
          onClick={() => dispatch(setTab("all"))}
          className={`px-4 py-2 rounded text-sm font-medium transition-colors ${tab === "all" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-700 hover:bg-gray-200"}`}
        >
          {t("tabs.all")}
        </button>
        <div className="ml-auto">
          <select
            value={clientFilter}
            onChange={(e) => setClientFilter(e.target.value)}
            className="border rounded px-3 py-2 text-sm bg-white min-w-[160px]"
          >
            <option value="">{t("filterAllClients")}</option>
            {clients.map((c) => (
              <option key={c._id} value={c._id}>{c.name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Records list */}
      {loading && <p className="text-gray-500 text-sm">{t("loadingRecords")}</p>}

      {!loading && records.length === 0 && (
        <div className="border border-dashed rounded-xl p-10 text-center text-gray-400 text-sm">
          {tab === "pending" ? t("emptyPending") : t("emptyAll")}
        </div>
      )}

      {!loading && records.length > 0 && (
        <div className="space-y-3">
          {records.map((r) => {
            const clientName = clients.find((c) => c._id === r.client_id)?.name;
            return (
              <Link
                key={r.id}
                href={`/campaigns/${r.id}`}
                className="block border rounded-lg p-4 hover:border-blue-300 hover:shadow-sm transition-all bg-white"
              >
                <div className="flex items-center gap-2 mb-2 flex-wrap">
                  <StatusBadge value={r.status} />
                  <ConfidenceBadge value={r.confidence} />
                  {r.meta?.campaign_type && (
                    <CampaignTypeBadge value={r.meta.campaign_type} />
                  )}
                  {r.meta?.industry && (
                    <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                      {r.meta.industry}
                    </span>
                  )}
                  {r.meta?.budget_tier && (
                    <BudgetTierBadge value={r.meta.budget_tier} />
                  )}
                </div>
                <div className="text-sm font-medium text-gray-800">
                  {(r.strategy_decisions?.big_idea as string) || t("noBigIdea")}
                </div>
                <div className="text-xs text-gray-500 mt-1.5 flex flex-wrap gap-3">
                  {clientName && (
                    <span className="flex items-center gap-1">
                      <svg viewBox="0 0 16 16" fill="currentColor" className="w-3 h-3 text-gray-400">
                        <path fillRule="evenodd" d="M4 4a2 2 0 012-2h8a2 2 0 012 2v12a1 1 0 110 2H4a1 1 0 110-2V4zm3 1h2v2H7V5zm2 4H7v2h2V9zm2-4h2v2h-2V5zm2 4h-2v2h2V9z" clipRule="evenodd" />
                      </svg>
                      {clientName}
                    </span>
                  )}
                  {r.meta?.target_audience_summary && (
                    <span>{r.meta.target_audience_summary}</span>
                  )}
                  {r.created_at && (
                    <span>{new Date(r.created_at).toLocaleDateString()}</span>
                  )}
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
