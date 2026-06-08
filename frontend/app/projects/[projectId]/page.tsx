"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { useTranslations } from "next-intl";

interface Project {
  _id: string;
  name: string;
  description?: string;
  deadline?: string;
  status: string;
  client_id: string;
  created_at: string;
}

interface Proposal {
  _id: string;
  proposal_id?: string;
  status?: string;
  created_at?: string;
  raw_brief?: string;
  output_language?: string;
}

interface Archive {
  _id: string;
  filename: string;
  status: string;
  uploaded_at: string;
}


// ── Status badge ──────────────────────────────────────────────────────────────

const statusColors: Record<string, string> = {
  draft: "bg-gray-100 text-gray-700",
  in_progress: "bg-blue-100 text-blue-700",
  completed: "bg-green-100 text-green-700",
  archived: "bg-yellow-100 text-yellow-700",
};

const archiveStatusColors: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-700",
  processing: "bg-blue-100 text-blue-700",
  done: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
};

// ── Overview / edit tab ───────────────────────────────────────────────────────

function OverviewTab({
  project,
  clientName,
  onUpdated,
}: {
  project: Project;
  clientName: string;
  onUpdated: (updated: Partial<Project>) => void;
}) {
  const t = useTranslations("projectDetail");
  const [name, setName] = useState(project.name);
  const [description, setDescription] = useState(project.description ?? "");
  const [deadline, setDeadline] = useState(project.deadline ?? "");
  const [projectStatus, setProjectStatus] = useState(project.status);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const dirty =
    name !== project.name ||
    description !== (project.description ?? "") ||
    deadline !== (project.deadline ?? "") ||
    projectStatus !== project.status;

  const handleSave = async () => {
    if (!name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const body: Record<string, string | null> = {
        name: name.trim(),
        description: description || null,
        deadline: deadline || null,
        status: projectStatus,
      };
      const res = await apiFetch(`/api/v1/projects/${project._id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(t("overview.saveFailed"));
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
      onUpdated({ name: name.trim(), description, deadline, status: projectStatus });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t("overview.saveFailed"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-5 max-w-lg">
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">{t("overview.nameLabel")}</label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full border rounded px-3 py-2 text-sm"
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">
          {t("overview.descLabel")} <span className="font-normal text-gray-400">{t("overview.descOptional")}</span>
        </label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
          placeholder={t("overview.descPlaceholder")}
          className="w-full border rounded px-3 py-2 text-sm resize-none"
        />
      </div>

      <div className="flex gap-4">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">
            {t("overview.deadlineLabel")} <span className="font-normal text-gray-400">{t("overview.deadlineOptional")}</span>
          </label>
          <input
            type="date"
            value={deadline}
            onChange={(e) => setDeadline(e.target.value)}
            className="border rounded px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">{t("overview.statusLabel")}</label>
          <select
            value={projectStatus}
            onChange={(e) => setProjectStatus(e.target.value)}
            className="border rounded px-3 py-2 text-sm bg-white"
          >
            <option value="draft">{t("overview.statusDraft")}</option>
            <option value="in_progress">{t("overview.statusInProgress")}</option>
            <option value="completed">{t("overview.statusCompleted")}</option>
            <option value="archived">{t("overview.statusArchived")}</option>
          </select>
        </div>
      </div>

      {/* Read-only meta */}
      <div className="border-t pt-4 space-y-1 text-xs text-gray-400">
        <p>
          <span className="font-medium text-gray-500">{t("overview.metaClient")}</span>
          <Link href={`/clients/${project.client_id}`} className="text-blue-500 hover:underline">
            {clientName || project.client_id}
          </Link>
        </p>
        <p>
          <span className="font-medium text-gray-500">{t("overview.metaProjectId")}</span>
          <button
            onClick={() => navigator.clipboard.writeText(project._id)}
            className="font-mono hover:text-gray-700 transition-colors"
            title={t("overview.clickToCopy")}
          >
            {project._id}
          </button>
        </p>
        <p>
          <span className="font-medium text-gray-500">{t("overview.metaCreated")}</span>
          {new Date(project.created_at).toLocaleDateString()}
        </p>
      </div>

      {error && <p className="text-red-500 text-sm">{error}</p>}

      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={saving || !dirty}
          className="px-5 py-2 bg-blue-600 text-white rounded text-sm font-medium disabled:opacity-40"
        >
          {saving ? t("overview.saving") : t("overview.saveChanges")}
        </button>
        {saved && <span className="text-green-600 text-sm">{t("overview.saved")}</span>}
        {!dirty && !saving && !saved && (
          <span className="text-gray-400 text-xs">{t("overview.noChanges")}</span>
        )}
      </div>
    </div>
  );
}

// ── Proposals tab ─────────────────────────────────────────────────────────────

function ProposalsTab({ project }: { project: Project }) {
  const t = useTranslations("projectDetail");
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch(`/api/v1/proposals?project_id=${project._id}`)
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => { if (Array.isArray(data)) setProposals(data); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [project._id]);

  if (loading) {
    return <p className="text-sm text-gray-400">{t("proposals.loading")}</p>;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <span className="text-sm text-gray-500">
          {proposals.length} proposal{proposals.length !== 1 ? "s" : ""}
        </span>
        <Link
          href={`/pipeline?client_id=${project.client_id}&project_id=${project._id}`}
          className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700 transition-colors"
        >
          {t("proposals.newProposal")}
        </Link>
      </div>

      {proposals.length === 0 ? (
        <div className="border border-dashed rounded-lg p-8 text-center text-gray-400 text-sm">
          {t("proposals.empty")}
          <br />
          <Link
            href={`/pipeline?client_id=${project.client_id}&project_id=${project._id}`}
            className="mt-3 inline-block text-blue-600 hover:underline"
          >
            {t("proposals.startNew")}
          </Link>
        </div>
      ) : (
        <div className="space-y-2">
          {proposals.map((p) => {
            const id = p.proposal_id ?? p._id;
            const brief = p.raw_brief ? p.raw_brief.slice(0, 100) + (p.raw_brief.length > 100 ? "…" : "") : "";
            return (
              <Link
                key={id}
                href={`/proposals/${id}`}
                className="block border rounded-lg p-4 hover:bg-gray-50 hover:border-blue-200 transition-colors group"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono text-xs text-gray-500">{id.slice(-12)}</span>
                      {p.status && (
                        <span className={`text-xs px-2 py-0.5 rounded ${statusColors[p.status] ?? "bg-gray-100 text-gray-600"}`}>
                          {p.status}
                        </span>
                      )}
                      {p.output_language && p.output_language !== "auto" && (
                        <span className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded">
                          {p.output_language === "zh" ? "中文" : "English"}
                        </span>
                      )}
                    </div>
                    {brief && (
                      <p className="text-sm text-gray-500 mt-1 line-clamp-2">{brief}</p>
                    )}
                    {p.created_at && (
                      <p className="text-xs text-gray-400 mt-1">
                        {new Date(p.created_at).toLocaleDateString()}
                      </p>
                    )}
                  </div>
                  <span className="shrink-0 text-sm text-gray-400 group-hover:text-blue-500 transition-colors">
                    {t("proposals.view")}
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Archive tab ───────────────────────────────────────────────────────────────

function ArchiveTab({ project }: { project: Project }) {
  const t = useTranslations("projectDetail");
  const [archives, setArchives] = useState<Archive[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadArchives = useCallback(async () => {
    try {
      const res = await apiFetch(`/api/v1/projects/${project._id}/archive`);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) setArchives(data);
      }
    } catch {}
    finally { setLoading(false); }
  }, [project._id]);

  useEffect(() => { loadArchives(); }, [loadArchives]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await apiFetch(`/api/v1/projects/${project._id}/archive`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail ?? "Upload failed");
      }
      await loadArchives();
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <div>
      {/* Upload area */}
      <div className="border-2 border-dashed rounded-lg p-6 mb-6 text-center bg-gray-50">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-8 h-8 text-gray-300 mx-auto mb-2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
        </svg>
        <p className="text-sm text-gray-500 mb-1">
          {t("archive.uploadTitle")}
        </p>
        <p className="text-xs text-gray-400 mb-3">{t("archive.uploadSubtitle")}</p>
        <label className={`inline-block px-4 py-2 rounded text-sm font-medium cursor-pointer transition-colors ${
          uploading ? "bg-gray-300 text-gray-500 cursor-wait" : "bg-blue-600 text-white hover:bg-blue-700"
        }`}>
          {uploading ? t("archive.uploading") : t("archive.chooseFile")}
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.pptx,.ppt"
            onChange={handleUpload}
            disabled={uploading}
            className="hidden"
          />
        </label>
        {uploadError && (
          <p className="mt-2 text-sm text-red-500">{uploadError}</p>
        )}
      </div>

      {/* Archive list */}
      {loading ? (
        <p className="text-sm text-gray-400">{t("archive.loading")}</p>
      ) : archives.length === 0 ? (
        <p className="text-sm text-gray-400">{t("archive.empty")}</p>
      ) : (
        <div className="space-y-2">
          {archives.map((a) => (
            <div key={a._id} className="border rounded-lg p-4 flex items-center justify-between gap-4">
              <div className="flex-1 min-w-0">
                <p className="font-medium text-sm truncate">{a.filename}</p>
                <p className="text-xs text-gray-400 mt-0.5">
                  {new Date(a.uploaded_at).toLocaleDateString()}
                </p>
              </div>
              <span className={`text-xs px-2 py-0.5 rounded shrink-0 ${archiveStatusColors[a.status] ?? "bg-gray-100 text-gray-600"}`}>
                {a.status}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

type Tab = "overview" | "proposals" | "archive";

export default function ProjectDetailPage() {
  const t = useTranslations("projectDetail");
  const { projectId } = useParams<{ projectId: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [clientName, setClientName] = useState("");
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [tab, setTab] = useState<Tab>("overview");

  const loadProject = useCallback(async () => {
    try {
      const res = await apiFetch(`/api/v1/projects/${projectId}`);
      if (!res.ok) { setNotFound(true); return; }
      const data = await res.json();
      setProject(data);
      // Fetch client name
      if (data.client_id) {
        apiFetch(`/api/v1/clients/${data.client_id}`)
          .then((r) => (r.ok ? r.json() : null))
          .then((c) => { if (c?.name) setClientName(c.name); })
          .catch(() => {});
      }
    } catch {
      setNotFound(true);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { loadProject(); }, [loadProject]);

  const handleUpdated = (updated: Partial<Project>) => {
    setProject((prev) => prev ? { ...prev, ...updated } : prev);
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto p-8">
        <p className="text-gray-400 text-sm">{t("loadingProject")}</p>
      </div>
    );
  }

  if (notFound || !project) {
    return (
      <div className="max-w-4xl mx-auto p-8">
        <p className="text-red-500 text-sm">{t("notFound")}</p>
        <Link href="/clients" className="text-blue-600 text-sm hover:underline mt-2 inline-block">
          {t("backToClients")}
        </Link>
      </div>
    );
  }

  const dl = project.deadline
    ? (() => {
        const diff = Math.ceil((new Date(project.deadline).getTime() - Date.now()) / 86400000);
        if (diff < 0) return { label: `${Math.abs(diff)}d overdue`, cls: "text-red-500" };
        if (diff === 0) return { label: "Due today", cls: "text-orange-500" };
        if (diff <= 7) return { label: `${diff}d left`, cls: "text-orange-500" };
        return { label: `${diff}d left`, cls: "text-gray-400" };
      })()
    : null;

  const tabLabels: Record<Tab, string> = {
    overview: t("tabOverview"),
    proposals: t("tabProposals"),
    archive: t("tabArchive"),
  };

  return (
    <div className="max-w-4xl mx-auto p-8">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm mb-2 flex-wrap">
        <Link href="/clients" className="text-blue-600 hover:underline">
          {t("breadcrumbClients")}
        </Link>
        <span className="text-gray-400">/</span>
        <Link href={`/clients/${project.client_id}`} className="text-blue-600 hover:underline">
          {clientName || project.client_id.slice(-8)}
        </Link>
        <span className="text-gray-400">/</span>
        <span className="text-gray-700 font-medium">{project.name}</span>
      </div>

      {/* Title row */}
      <div className="flex items-center gap-3 mb-1 flex-wrap">
        <h1 className="text-2xl font-bold">{project.name}</h1>
        <span className={`text-xs px-2 py-0.5 rounded ${statusColors[project.status] ?? "bg-gray-100 text-gray-600"}`}>
          {project.status}
        </span>
        {dl && <span className={`text-xs font-medium ${dl.cls}`}>{dl.label}</span>}
      </div>
      {project.description && (
        <p className="text-sm text-gray-500 mb-5">{project.description}</p>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b mb-6">
        {(["overview", "proposals", "archive"] as Tab[]).map((tabKey) => (
          <button
            key={tabKey}
            onClick={() => setTab(tabKey)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === tabKey
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-800"
            }`}
          >
            {tabLabels[tabKey]}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <OverviewTab project={project} clientName={clientName} onUpdated={handleUpdated} />
      )}
      {tab === "proposals" && <ProposalsTab project={project} />}
      {tab === "archive" && <ArchiveTab project={project} />}
    </div>
  );
}
