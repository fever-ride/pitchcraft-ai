"use client";

import Link from "next/link";
import { useEffect, useRef, useState, useCallback } from "react";
import { useDispatch, useSelector } from "react-redux";
import { useTranslations } from "next-intl";

import type { AppDispatch, RootState } from "@/store/store";
import { fetchRecords, setTab } from "@/store/campaignsSlice";
import { apiFetch } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────────────

interface Client {
  _id: string;
  name: string;
  industry: string | null;
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

// ── Upload panel ───────────────────────────────────────────────────────────────

function UploadPanel({ onUploaded, resetSignal }: { onUploaded: () => void; resetSignal?: number }) {
  const t = useTranslations("campaigns");
  const tc = useTranslations("common");
  const [clients, setClients] = useState<Client[]>([]);
  const [clientId, setClientId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<"idle" | "processing" | "error">("idle");

  // Clear banner when parent detects the new record arrived
  useEffect(() => {
    if (resetSignal) setUploadStatus("idle");
  }, [resetSignal]);
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
    setUploadStatus("idle");
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
      setUploadStatus("processing");
      setFile(null);
      if (fileRef.current) fileRef.current.value = "";
      onUploaded();
    } catch (e: unknown) {
      setUploadStatus("error");
      setErrorMsg(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const selectedClientName = clients.find((c) => c._id === clientId)?.name;

  return (
    <div className="border rounded-xl bg-white p-6 mb-8 shadow-sm">
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

      {/* Status feedback */}
      {uploadStatus === "processing" && (
        <div className="mt-3 flex items-center gap-2 text-sm text-blue-700 bg-blue-50 border border-blue-200 rounded px-3 py-2">
          <svg className="animate-spin w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
          </svg>
          {t("upload.processingMsg")}
        </div>
      )}
      {uploadStatus === "error" && (
        <p className="mt-3 text-sm text-red-600">{errorMsg}</p>
      )}
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function CampaignsPage() {
  const dispatch = useDispatch<AppDispatch>();
  const { records, loading, tab } = useSelector((state: RootState) => state.campaigns);
  const t = useTranslations("campaigns");

  const [clients, setClients] = useState<Client[]>([]);
  const [clientFilter, setClientFilter] = useState("");

  // Polling after upload
  const [polling, setPolling] = useState(false);
  const [panelReset, setPanelReset] = useState(0);
  const pollCountRef = useRef(0);
  const prevPendingCount = useRef<number | null>(null);

  useEffect(() => {
    apiFetch("/api/v1/clients")
      .then((r) => (r.ok ? r.json() : []))
      .then((data: Client[]) => { if (Array.isArray(data)) setClients(data); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    dispatch(fetchRecords({ tab, clientId: clientFilter || undefined }));
  }, [dispatch, tab, clientFilter]);

  useEffect(() => {
    if (!polling) return;
    const interval = setInterval(() => {
      pollCountRef.current += 1;
      dispatch(fetchRecords({ tab: "pending", clientId: clientFilter || undefined }));
      if (pollCountRef.current >= 36) {
        setPolling(false);
        pollCountRef.current = 0;
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [polling, dispatch, clientFilter]);

  const pendingCount = records.filter((r) => r.status === "pending_confirmation").length;
  useEffect(() => {
    if (!polling) return;
    if (prevPendingCount.current === null) { prevPendingCount.current = pendingCount; return; }
    if (pendingCount > prevPendingCount.current) {
      setPolling(false);
      setPanelReset(v => v + 1);
      pollCountRef.current = 0;
      prevPendingCount.current = null;
    }
  }, [pendingCount, polling]);

  const reload = useCallback(() => {
    dispatch(fetchRecords({ tab, clientId: clientFilter || undefined }));
    dispatch(setTab("pending"));
    setPolling(true);
    pollCountRef.current = 0;
    prevPendingCount.current = null;
  }, [dispatch, tab, clientFilter]);

  return (
    <div className="max-w-5xl mx-auto p-8">
      <h1 className="text-2xl font-bold mb-1">{t("title")}</h1>
      <p className="text-sm text-gray-500 mb-6">{t("subtitle")}</p>

      <UploadPanel onUploaded={reload} resetSignal={panelReset} />

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

      {/* Polling indicator */}
      {polling && (
        <div className="flex items-center gap-2 text-sm text-blue-600 mb-4">
          <svg className="animate-spin w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
          </svg>
          {t("polling")}
        </div>
      )}

      {/* Records list */}
      {loading && !polling && <p className="text-gray-500 text-sm">{t("loadingRecords")}</p>}

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
