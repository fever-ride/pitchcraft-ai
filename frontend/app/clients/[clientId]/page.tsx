"use client";

import { useState, useEffect, useCallback } from "react";
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
  created_at: string;
}

interface BrandProfile {
  brand_name?: string;
  positioning?: string;
  personality: string[];
  target_audience?: string;
  usage_scenes: string[];
  user_pain_points: string[];
  rtb: string[];
  tone_principles: string[];
  forbidden_directions: string[];
  key_messages: string[];
  competitive_position?: string;
  approved_directions: string[];
  rejected_directions: string[];
}

const EMPTY_PROFILE: BrandProfile = {
  brand_name: "",
  positioning: "",
  personality: [],
  target_audience: "",
  usage_scenes: [],
  user_pain_points: [],
  rtb: [],
  tone_principles: [],
  forbidden_directions: [],
  key_messages: [],
  competitive_position: "",
  approved_directions: [],
  rejected_directions: [],
};

// ── Small helpers ─────────────────────────────────────────────────────────────

function ListInput({
  label,
  hint,
  items,
  onChange,
  placeholder,
  readonly,
  addLabel,
}: {
  label: string;
  hint?: string;
  items: string[];
  onChange?: (items: string[]) => void;
  placeholder?: string;
  readonly?: boolean;
  addLabel?: string;
}) {
  const handleChange = (i: number, val: string) => {
    const next = [...items];
    next[i] = val;
    onChange?.(next);
  };
  const handleAdd = () => onChange?.([...items, ""]);
  const handleRemove = (i: number) => onChange?.(items.filter((_, idx) => idx !== i));

  return (
    <div>
      <label className="text-xs text-gray-500 block mb-1">
        {label}
        {hint && <span className="text-gray-400 ml-1">{hint}</span>}
      </label>
      {readonly ? (
        items.length > 0 ? (
          <ul className="text-sm text-gray-800 list-disc list-inside space-y-0.5">
            {items.map((item, i) => <li key={i}>{item}</li>)}
          </ul>
        ) : (
          <span className="text-sm text-gray-400">—</span>
        )
      ) : (
        <div className="space-y-1">
          {items.map((item, i) => (
            <div key={i} className="flex gap-1">
              <input
                type="text"
                value={item}
                onChange={(e) => handleChange(i, e.target.value)}
                placeholder={placeholder}
                className="flex-1 border rounded px-2 py-1 text-sm"
              />
              <button
                type="button"
                onClick={() => handleRemove(i)}
                className="text-gray-400 hover:text-red-500 px-1 text-xs"
              >
                ✕
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={handleAdd}
            className="text-xs text-blue-600 hover:underline"
          >
            {addLabel || "+ Add"}
          </button>
        </div>
      )}
    </div>
  );
}

// ── Projects tab ──────────────────────────────────────────────────────────────

function ProjectsTab({ clientId }: { clientId: string }) {
  const t = useTranslations("clientDetail");
  const tp = t as unknown as (key: string, values?: Record<string, string | number>) => string;
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectName, setProjectName] = useState("");
  const [projectDescription, setProjectDescription] = useState("");
  const [projectDeadline, setProjectDeadline] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [creating, setCreating] = useState(false);

  const loadProjects = useCallback(async () => {
    try {
      const res = await apiFetch(`/api/v1/projects?client_id=${clientId}`);
      if (!res.ok) return;
      const data = await res.json();
      if (Array.isArray(data)) setProjects(data);
    } catch {}
  }, [clientId]);

  useEffect(() => { loadProjects(); }, [loadProjects]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectName.trim()) return;
    setCreating(true);
    try {
      const res = await apiFetch("/api/v1/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: clientId,
          name: projectName,
          description: projectDescription,
          deadline: projectDeadline,
        }),
      });
      if (!res.ok) return;
      setProjectName("");
      setProjectDescription("");
      setProjectDeadline("");
      setShowForm(false);
      await loadProjects();
    } finally {
      setCreating(false);
    }
  };

  const statusColor: Record<string, string> = {
    draft: "bg-gray-100 text-gray-700",
    in_progress: "bg-blue-100 text-blue-700",
    completed: "bg-green-100 text-green-700",
    archived: "bg-yellow-100 text-yellow-700",
  };

  // Days until deadline helper
  const daysUntil = (iso: string) => {
    const diff = Math.ceil((new Date(iso).getTime() - Date.now()) / 86400000);
    if (diff < 0) return { label: tp("projects.daysOverdue", { count: Math.abs(diff) }), cls: "text-red-500" };
    if (diff === 0) return { label: t("projects.dueToday"), cls: "text-orange-500" };
    if (diff <= 7) return { label: tp("projects.daysLeft", { count: diff }), cls: "text-orange-500" };
    return { label: tp("projects.daysLeft", { count: diff }), cls: "text-gray-400" };
  };

  return (
    <div>
      {/* Header row */}
      <div className="flex items-center justify-between mb-6">
        <span className="text-sm text-gray-500">{projects.length} project{projects.length !== 1 ? "s" : ""}</span>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700 transition-colors"
        >
          {showForm ? t("projects.cancelCreate") : t("projects.newProject")}
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <form onSubmit={handleCreate} className="border rounded-lg p-4 mb-6 bg-gray-50 space-y-3">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">{t("projects.formNameLabel")}</label>
            <input
              type="text"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              placeholder={t("projects.formNamePlaceholder")}
              className="w-full border rounded px-3 py-2 text-sm bg-white"
              required
              autoFocus
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              {t("projects.formDescLabel")} <span className="font-normal text-gray-400">{t("projects.formDescOptional")}</span>
            </label>
            <textarea
              value={projectDescription}
              onChange={(e) => setProjectDescription(e.target.value)}
              placeholder={t("projects.formDescPlaceholder")}
              className="w-full border rounded px-3 py-2 text-sm bg-white resize-none"
              rows={2}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              {t("projects.formDeadlineLabel")} <span className="font-normal text-gray-400">{t("projects.formDeadlineOptional")}</span>
            </label>
            <input
              type="date"
              value={projectDeadline}
              onChange={(e) => setProjectDeadline(e.target.value)}
              className="border rounded px-3 py-2 text-sm bg-white"
            />
          </div>
          <div className="flex gap-2 pt-1">
            <button
              type="submit"
              disabled={creating}
              className="px-4 py-2 bg-blue-600 text-white rounded text-sm font-medium disabled:opacity-50"
            >
              {creating ? t("projects.creating") : t("projects.createProject")}
            </button>
          </div>
        </form>
      )}

      {/* Project list */}
      {projects.length === 0 && !showForm ? (
        <p className="text-gray-400 text-sm">{t("projects.noProjects")}</p>
      ) : (
        <div className="space-y-2">
          {projects.map((project) => {
            const dl = project.deadline ? daysUntil(project.deadline) : null;
            return (
              <Link
                key={project._id}
                href={`/projects/${project._id}`}
                className="block border rounded-lg p-4 hover:bg-gray-50 hover:border-blue-200 transition-colors group"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-medium text-gray-900 group-hover:text-blue-600 transition-colors">{project.name}</h3>
                      <span className={`text-xs px-2 py-0.5 rounded ${statusColor[project.status] || "bg-gray-100 text-gray-600"}`}>
                        {project.status}
                      </span>
                      {dl && <span className={`text-xs ${dl.cls}`}>{dl.label}</span>}
                    </div>
                    {project.description && (
                      <p className="text-sm text-gray-500 mt-1 truncate">{project.description}</p>
                    )}
                    <p className="mt-1.5 font-mono text-xs text-gray-400">
                      ID: {project._id.slice(-8)}
                    </p>
                  </div>
                  <span className="shrink-0 px-3 py-1.5 text-sm border rounded text-gray-500 group-hover:bg-blue-50 group-hover:border-blue-300 group-hover:text-blue-600 transition-colors">
                    {t("projects.openProject")}
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

// ── Brand Profile tab ─────────────────────────────────────────────────────────

function BrandProfileTab({ clientId }: { clientId: string }) {
  const t = useTranslations("clientDetail");
  const bp = (key: string) => t(`brandProfile.${key}` as Parameters<typeof t>[0]);
  const [profile, setProfile] = useState<BrandProfile>(EMPTY_PROFILE);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [extractText, setExtractText] = useState("");
  const [extracting, setExtracting] = useState(false);
  const [extractDraft, setExtractDraft] = useState<Partial<BrandProfile> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadProfile = useCallback(async () => {
    try {
      const res = await apiFetch(`/api/v1/clients/${clientId}/brand-profile`);
      if (res.ok) {
        const data = await res.json();
        setProfile({
          brand_name: data.brand_name || "",
          positioning: data.positioning || "",
          personality: data.personality || [],
          target_audience: data.target_audience || "",
          usage_scenes: data.usage_scenes || [],
          user_pain_points: data.user_pain_points || [],
          rtb: data.rtb || [],
          tone_principles: data.tone_principles || [],
          forbidden_directions: data.forbidden_directions || [],
          key_messages: data.key_messages || [],
          competitive_position: data.competitive_position || "",
          approved_directions: data.approved_directions || [],
          rejected_directions: data.rejected_directions || [],
        });
      }
      // 404 = no profile yet, keep empty form
    } catch {}
  }, [clientId]);

  useEffect(() => { loadProfile(); }, [loadProfile]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/v1/clients/${clientId}/brand-profile`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(profile),
      });
      if (!res.ok) throw new Error(bp("saveFailed"));
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : bp("saveFailed"));
    } finally {
      setSaving(false);
    }
  };

  const handleExtract = async () => {
    if (!extractText.trim()) return;
    setExtracting(true);
    setExtractDraft(null);
    setError(null);
    try {
      const form = new FormData();
      form.append("text", extractText);
      const res = await apiFetch(`/api/v1/clients/${clientId}/brand-profile/extract`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) throw new Error(bp("extractFailed"));
      const draft = await res.json();
      setExtractDraft(draft);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : bp("extractFailed"));
    } finally {
      setExtracting(false);
    }
  };

  const applyDraft = () => {
    if (!extractDraft) return;
    setProfile((prev) => ({
      ...prev,
      brand_name: extractDraft.brand_name || prev.brand_name,
      positioning: extractDraft.positioning || prev.positioning,
      personality: extractDraft.personality?.length ? extractDraft.personality : prev.personality,
      target_audience: extractDraft.target_audience || prev.target_audience,
      usage_scenes: extractDraft.usage_scenes?.length ? extractDraft.usage_scenes : prev.usage_scenes,
      user_pain_points: extractDraft.user_pain_points?.length ? extractDraft.user_pain_points : prev.user_pain_points,
      rtb: extractDraft.rtb?.length ? extractDraft.rtb : prev.rtb,
      tone_principles: extractDraft.tone_principles?.length ? extractDraft.tone_principles : prev.tone_principles,
      forbidden_directions: extractDraft.forbidden_directions?.length ? extractDraft.forbidden_directions : prev.forbidden_directions,
      key_messages: extractDraft.key_messages?.length ? extractDraft.key_messages : prev.key_messages,
      competitive_position: extractDraft.competitive_position || prev.competitive_position,
    }));
    setExtractDraft(null);
    setExtractText("");
  };

  const set = (field: keyof BrandProfile, value: unknown) =>
    setProfile((p) => ({ ...p, [field]: value }));

  return (
    <div className="space-y-8">

      {/* Extract from text */}
      <div className="border rounded p-4 bg-gray-50">
        <h3 className="text-sm font-medium mb-1">{bp("extractTitle")}</h3>
        <p className="text-xs text-gray-500 mb-3">
          {bp("extractSubtitle")}
        </p>
        <textarea
          value={extractText}
          onChange={(e) => setExtractText(e.target.value)}
          placeholder={bp("extractPlaceholder")}
          className="w-full border rounded px-3 py-2 text-sm min-h-[100px] resize-y bg-white"
        />
        <div className="mt-2 flex items-center gap-3">
          <button
            type="button"
            onClick={handleExtract}
            disabled={extracting || !extractText.trim()}
            className="px-4 py-1.5 bg-gray-800 text-white rounded text-sm disabled:opacity-50"
          >
            {extracting ? bp("extracting") : bp("extractButton")}
          </button>
          {extractDraft && (
            <span className="text-xs text-green-600">
              {bp("extractDone")}
            </span>
          )}
        </div>

        {/* Extraction draft preview */}
        {extractDraft && (
          <div className="mt-4 border rounded p-3 bg-white space-y-2">
            <p className="text-xs font-medium text-gray-600 mb-2">{bp("extractedDraft")}</p>
            {extractDraft.brand_name && <p className="text-sm"><span className="text-xs text-gray-500">{bp("extractLabel.brandName")}</span>{extractDraft.brand_name}</p>}
            {extractDraft.positioning && <p className="text-sm"><span className="text-xs text-gray-500">{bp("extractLabel.positioning")}</span>{extractDraft.positioning}</p>}
            {!!extractDraft.personality?.length && <p className="text-sm"><span className="text-xs text-gray-500">{bp("extractLabel.personality")}</span>{extractDraft.personality.join(", ")}</p>}
            {extractDraft.target_audience && <p className="text-sm"><span className="text-xs text-gray-500">{bp("extractLabel.audience")}</span>{extractDraft.target_audience}</p>}
            {!!extractDraft.usage_scenes?.length && <p className="text-sm"><span className="text-xs text-gray-500">{bp("extractLabel.usageScenes")}</span>{extractDraft.usage_scenes.join(" · ")}</p>}
            {!!extractDraft.user_pain_points?.length && <p className="text-sm"><span className="text-xs text-gray-500">{bp("extractLabel.painPoints")}</span>{extractDraft.user_pain_points.join(" · ")}</p>}
            {!!extractDraft.rtb?.length && <p className="text-sm"><span className="text-xs text-gray-500">{bp("extractLabel.rtb")}</span>{extractDraft.rtb.join(" · ")}</p>}
            {!!extractDraft.tone_principles?.length && <p className="text-sm"><span className="text-xs text-gray-500">{bp("extractLabel.tone")}</span>{extractDraft.tone_principles.join(" · ")}</p>}
            {!!extractDraft.forbidden_directions?.length && <p className="text-sm"><span className="text-xs text-gray-500">{bp("extractLabel.forbidden")}</span>{extractDraft.forbidden_directions.join(" · ")}</p>}
            {!!extractDraft.key_messages?.length && <p className="text-sm"><span className="text-xs text-gray-500">{bp("extractLabel.keyMessages")}</span>{extractDraft.key_messages.join(" · ")}</p>}
            <div className="flex gap-2 mt-3">
              <button
                type="button"
                onClick={applyDraft}
                className="px-3 py-1 bg-blue-600 text-white rounded text-xs"
              >
                {bp("applyToForm")}
              </button>
              <button
                type="button"
                onClick={() => setExtractDraft(null)}
                className="px-3 py-1 border rounded text-xs text-gray-600"
              >
                {bp("discard")}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Profile form */}
      <div className="space-y-5">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-xs text-gray-500 block mb-1">{bp("brandName")}</label>
            <input
              type="text"
              value={profile.brand_name || ""}
              onChange={(e) => set("brand_name", e.target.value)}
              className="w-full border rounded px-2 py-1 text-sm"
            />
          </div>
        </div>

        <div>
          <label className="text-xs text-gray-500 block mb-1">{bp("positioning")} <span className="text-gray-400">{bp("positioningHint")}</span></label>
          <textarea
            value={profile.positioning || ""}
            onChange={(e) => set("positioning", e.target.value)}
            className="w-full border rounded px-2 py-1 text-sm min-h-[60px] resize-y"
          />
        </div>

        <div>
          <label className="text-xs text-gray-500 block mb-1">{bp("targetAudience")}</label>
          <textarea
            value={profile.target_audience || ""}
            onChange={(e) => set("target_audience", e.target.value)}
            className="w-full border rounded px-2 py-1 text-sm min-h-[50px] resize-y"
          />
        </div>

        <ListInput
          label={bp("usageScenes")}
          hint={bp("usageScenesHint")}
          items={profile.usage_scenes}
          onChange={(v) => set("usage_scenes", v)}
          placeholder="e.g. 通勤护肤"
          addLabel={bp("addItem")}
        />

        <ListInput
          label={bp("userPainPoints")}
          hint={bp("userPainPointsHint")}
          items={profile.user_pain_points}
          onChange={(v) => set("user_pain_points", v)}
          placeholder="e.g. 工作后肌肤疲惫暗沉"
          addLabel={bp("addItem")}
        />

        <ListInput
          label={bp("rtb")}
          hint={bp("rtbHint")}
          items={profile.rtb}
          onChange={(v) => set("rtb", v)}
          placeholder="e.g. 法国首席调香师团队"
          addLabel={bp("addItem")}
        />

        <div>
          <label className="text-xs text-gray-500 block mb-1">{bp("competitivePosition")} <span className="text-gray-400">{bp("competitivePositionHint")}</span></label>
          <textarea
            value={profile.competitive_position || ""}
            onChange={(e) => set("competitive_position", e.target.value)}
            className="w-full border rounded px-2 py-1 text-sm min-h-[50px] resize-y"
          />
        </div>

        <ListInput
          label={bp("personality")}
          hint={bp("personalityHint")}
          items={profile.personality}
          onChange={(v) => set("personality", v)}
          placeholder="e.g. 权威"
          addLabel={bp("addItem")}
        />

        <ListInput
          label={bp("tonePrinciples")}
          hint={bp("tonePrinciplesHint")}
          items={profile.tone_principles}
          onChange={(v) => set("tone_principles", v)}
          placeholder="e.g. 避免娱乐化表达"
          addLabel={bp("addItem")}
        />

        <ListInput
          label={bp("forbiddenDirections")}
          hint={bp("forbiddenDirectionsHint")}
          items={profile.forbidden_directions}
          onChange={(v) => set("forbidden_directions", v)}
          placeholder="e.g. 不用竞品名字对比"
          addLabel={bp("addItem")}
        />

        <ListInput
          label={bp("keyMessages")}
          hint={bp("keyMessagesHint")}
          items={profile.key_messages}
          onChange={(v) => set("key_messages", v)}
          placeholder="e.g. 专业运动装备首选"
          addLabel={bp("addItem")}
        />

        {/* Read-only: populated from feedback loop */}
        {(profile.approved_directions.length > 0 || profile.rejected_directions.length > 0) && (
          <div className="border-t pt-4 space-y-4">
            <p className="text-xs text-gray-400">{bp("feedbackNote")}</p>
            <ListInput label={bp("approvedDirections")} items={profile.approved_directions} readonly />
            <ListInput label={bp("rejectedDirections")} items={profile.rejected_directions} readonly />
          </div>
        )}
      </div>

      {error && <p className="text-red-500 text-sm">{error}</p>}

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="px-5 py-2 bg-blue-600 text-white rounded text-sm font-medium disabled:opacity-50"
        >
          {saving ? bp("saving") : bp("saveBrandProfile")}
        </button>
        {saved && <span className="text-green-600 text-sm">{bp("saved")}</span>}
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ClientDetailPage() {
  const t = useTranslations("clientDetail");
  const { clientId } = useParams<{ clientId: string }>();
  const [tab, setTab] = useState<"projects" | "brand-profile">("projects");
  const [clientName, setClientName] = useState<string>("");

  useEffect(() => {
    apiFetch(`/api/v1/clients/${clientId}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => { if (data?.name) setClientName(data.name); })
      .catch(() => {});
  }, [clientId]);

  return (
    <div className="max-w-4xl mx-auto p-8">
      <div className="flex items-center gap-2 mb-6">
        <Link href="/clients" className="text-blue-600 text-sm hover:underline">
          {t("breadcrumbClients")}
        </Link>
        <span className="text-gray-400">/</span>
        <h1 className="text-2xl font-bold">{clientName || "…"}</h1>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b mb-6">
        {(["projects", "brand-profile"] as const).map((tabKey) => (
          <button
            key={tabKey}
            onClick={() => setTab(tabKey)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === tabKey
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-800"
            }`}
          >
            {tabKey === "projects" ? t("tabProjects") : t("tabBrandProfile")}
          </button>
        ))}
      </div>

      {tab === "projects" && <ProjectsTab clientId={clientId} />}
      {tab === "brand-profile" && <BrandProfileTab clientId={clientId} />}
    </div>
  );
}
