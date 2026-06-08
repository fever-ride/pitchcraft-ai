"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Client {
  _id: string;
  name: string;
  industry: string | null;
}

interface Project {
  _id: string;
  name: string;
  status: string;
}

interface Props {
  onSubmit: (brief: string, clientId: string, projectId: string, outputLanguage: string) => void;
  initialClientId?: string;
  initialProjectId?: string;
}

function authHeaders(): Record<string, string> {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function BriefInput({ onSubmit, initialClientId, initialProjectId }: Props) {
  const t = useTranslations("pipeline");
  const [brief, setBrief] = useState("");
  const [outputLanguage, setOutputLanguage] = useState("auto");
  const [submitting, setSubmitting] = useState(false);

  // Client
  const [clients, setClients] = useState<Client[]>([]);
  const [clientId, setClientId] = useState(initialClientId ?? "");
  const [clientsLoading, setClientsLoading] = useState(true);

  // Project
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectsLoading, setProjectsLoading] = useState(false);
  // "" = no project, "new" = create new, any other string = existing project _id
  const [projectSelection, setProjectSelection] = useState("");
  const [newProjectName, setNewProjectName] = useState("");

  // Load clients on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/v1/clients`, { headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => { if (Array.isArray(data)) setClients(data); })
      .catch(() => {})
      .finally(() => setClientsLoading(false));
  }, []);

  // Load projects whenever client changes
  useEffect(() => {
    if (!clientId) { setProjects([]); setProjectSelection(""); return; }
    setProjectsLoading(true);
    setProjectSelection("");
    fetch(`${API_BASE}/api/v1/projects?client_id=${clientId}`, { headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => {
        if (Array.isArray(data)) {
          setProjects(data);
          if (initialProjectId && clientId === initialClientId) {
            setProjectSelection(initialProjectId);
          }
        }
      })
      .catch(() => {})
      .finally(() => setProjectsLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!brief.trim() || !clientId) return;
    setSubmitting(true);
    try {
      let projectId = "";

      if (projectSelection === "new") {
        // Create the project first, then use its ID
        const name = newProjectName.trim() || "Untitled Project";
        const res = await fetch(`${API_BASE}/api/v1/projects`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders() },
          body: JSON.stringify({ client_id: clientId, name }),
        });
        if (res.ok) {
          const data = await res.json();
          projectId = data.project_id ?? "";
        }
      } else if (projectSelection) {
        projectId = projectSelection;
      }

      onSubmit(brief, clientId, projectId, outputLanguage);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5">

      {/* Client */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          {t("briefInput.clientLabel")} <span className="text-red-500">{t("briefInput.clientRequired")}</span>
        </label>
        {clientsLoading ? (
          <div className="border rounded px-3 py-2 text-sm text-gray-400">{t("briefInput.clientsLoading")}</div>
        ) : clients.length === 0 ? (
          <div className="border border-amber-200 bg-amber-50 rounded px-3 py-2 text-sm text-amber-700">
            {t("briefInput.noClients")}{" "}
            <a href="/clients" className="underline font-medium">{t("briefInput.createClientLink")}</a>
          </div>
        ) : (
          <select
            value={clientId}
            onChange={(e) => setClientId(e.target.value)}
            className="w-full border rounded px-3 py-2 text-sm bg-white"
            required
          >
            <option value="">{t("briefInput.selectClient")}</option>
            {clients.map((c) => (
              <option key={c._id} value={c._id}>
                {c.name}{c.industry ? ` · ${c.industry}` : ""}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Project (only shown once a client is selected) */}
      {clientId && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t("briefInput.projectLabel")}
            <span className="ml-1 text-xs font-normal text-gray-400">{t("briefInput.projectOptional")}</span>
          </label>
          {projectsLoading ? (
            <div className="border rounded px-3 py-2 text-sm text-gray-400">{t("briefInput.projectsLoading")}</div>
          ) : (
            <select
              value={projectSelection}
              onChange={(e) => setProjectSelection(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm bg-white"
            >
              <option value="">{t("briefInput.noProject")}</option>
              {projects.map((p) => (
                <option key={p._id} value={p._id}>
                  {p.name}
                  {p.status && p.status !== "draft" ? ` (${p.status})` : ""}
                </option>
              ))}
              <option value="new">{t("briefInput.createNewProject")}</option>
            </select>
          )}

          {projectSelection === "new" && (
            <input
              type="text"
              value={newProjectName}
              onChange={(e) => setNewProjectName(e.target.value)}
              placeholder={t("briefInput.newProjectPlaceholder")}
              className="mt-2 w-full border rounded px-3 py-2 text-sm"
              autoFocus
            />
          )}
        </div>
      )}

      {/* Output language */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          {t("briefInput.outputLanguageLabel")}
        </label>
        <select
          value={outputLanguage}
          onChange={(e) => setOutputLanguage(e.target.value)}
          className="w-full border rounded px-3 py-2 text-sm bg-white"
        >
          <option value="auto">{t("briefInput.outputLanguageAuto")}</option>
          <option value="en">{t("briefInput.outputLanguageEn")}</option>
          <option value="zh">{t("briefInput.outputLanguageZh")}</option>
        </select>
        <p className="text-xs text-gray-400 mt-1">
          {t("briefInput.outputLanguageHint")}
        </p>
      </div>

      {/* Brief */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          {t("briefInput.briefLabel")} <span className="text-red-500">{t("briefInput.briefRequired")}</span>
        </label>
        <textarea
          value={brief}
          onChange={(e) => setBrief(e.target.value)}
          rows={10}
          className="w-full border rounded px-3 py-2 text-sm resize-y"
          placeholder={t("briefInput.briefPlaceholder")}
          required
        />
      </div>

      <button
        type="submit"
        disabled={!clientId || !brief.trim() || submitting}
        className="w-full py-2.5 bg-blue-600 text-white rounded font-medium hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        {submitting ? t("briefInput.starting") : t("briefInput.startPipeline")}
      </button>
    </form>
  );
}
