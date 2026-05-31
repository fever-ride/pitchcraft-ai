"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Project {
  _id: string;
  name: string;
  status: string;
  created_at: string;
}

interface BrandProfile {
  brand_name?: string;
  positioning?: string;
  personality: string[];
  target_audience?: string;
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
}: {
  label: string;
  hint?: string;
  items: string[];
  onChange?: (items: string[]) => void;
  placeholder?: string;
  readonly?: boolean;
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
            + Add
          </button>
        </div>
      )}
    </div>
  );
}

// ── Projects tab ──────────────────────────────────────────────────────────────

function ProjectsTab({ clientId }: { clientId: string }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectName, setProjectName] = useState("");
  const [creating, setCreating] = useState(false);

  const headers = () => ({
    "Content-Type": "application/json",
    Authorization: `Bearer ${localStorage.getItem("token")}`,
  });

  const loadProjects = useCallback(async () => {
    try {
      const data = await fetch(
        `${API_BASE}/api/v1/projects?client_id=${clientId}`,
        { headers: headers() }
      ).then((r) => r.json());
      setProjects(data);
    } catch {}
  }, [clientId]);

  useEffect(() => { loadProjects(); }, [loadProjects]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectName.trim()) return;
    setCreating(true);
    try {
      await fetch(`${API_BASE}/api/v1/projects`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ client_id: clientId, name: projectName }),
      });
      setProjectName("");
      loadProjects();
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

  return (
    <div>
      <form onSubmit={handleCreate} className="flex gap-3 mb-8">
        <input
          type="text"
          value={projectName}
          onChange={(e) => setProjectName(e.target.value)}
          placeholder="New project name"
          className="border rounded px-3 py-2 text-sm flex-1"
          required
        />
        <button
          type="submit"
          disabled={creating}
          className="px-4 py-2 bg-blue-600 text-white rounded text-sm font-medium"
        >
          Create Project
        </button>
      </form>

      {projects.length === 0 ? (
        <p className="text-gray-500 text-sm">No projects yet for this client.</p>
      ) : (
        <div className="space-y-2">
          {projects.map((project) => (
            <Link
              key={project._id}
              href={`/pipeline?client_id=${clientId}&project_id=${project._id}`}
              className="block border rounded p-4 hover:bg-gray-50 transition-colors"
            >
              <div className="flex items-center justify-between">
                <h3 className="font-medium">{project.name}</h3>
                <span className={`text-xs px-2 py-0.5 rounded ${statusColor[project.status] || "bg-gray-100"}`}>
                  {project.status}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Brand Profile tab ─────────────────────────────────────────────────────────

function BrandProfileTab({ clientId }: { clientId: string }) {
  const [profile, setProfile] = useState<BrandProfile>(EMPTY_PROFILE);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [extractText, setExtractText] = useState("");
  const [extracting, setExtracting] = useState(false);
  const [extractDraft, setExtractDraft] = useState<Partial<BrandProfile> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const headers = (contentType = "application/json") => ({
    "Content-Type": contentType,
    Authorization: `Bearer ${localStorage.getItem("token")}`,
  });

  const loadProfile = useCallback(async () => {
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/clients/${clientId}/brand-profile`,
        { headers: headers() }
      );
      if (res.ok) {
        const data = await res.json();
        setProfile({
          brand_name: data.brand_name || "",
          positioning: data.positioning || "",
          personality: data.personality || [],
          target_audience: data.target_audience || "",
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
      const res = await fetch(
        `${API_BASE}/api/v1/clients/${clientId}/brand-profile`,
        {
          method: "PUT",
          headers: headers(),
          body: JSON.stringify(profile),
        }
      );
      if (!res.ok) throw new Error("Save failed");
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed");
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
      const res = await fetch(
        `${API_BASE}/api/v1/clients/${clientId}/brand-profile/extract`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
          body: form,
        }
      );
      if (!res.ok) throw new Error("Extraction failed");
      const draft = await res.json();
      setExtractDraft(draft);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Extraction failed");
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
        <h3 className="text-sm font-medium mb-1">Extract from brand document</h3>
        <p className="text-xs text-gray-500 mb-3">
          Paste text from a brand handbook or guidelines document. The system will extract the relevant fields — you can review and edit before saving.
        </p>
        <textarea
          value={extractText}
          onChange={(e) => setExtractText(e.target.value)}
          placeholder="Paste brand document text here..."
          className="w-full border rounded px-3 py-2 text-sm min-h-[100px] resize-y bg-white"
        />
        <div className="mt-2 flex items-center gap-3">
          <button
            type="button"
            onClick={handleExtract}
            disabled={extracting || !extractText.trim()}
            className="px-4 py-1.5 bg-gray-800 text-white rounded text-sm disabled:opacity-50"
          >
            {extracting ? "Extracting..." : "Extract"}
          </button>
          {extractDraft && (
            <span className="text-xs text-green-600">
              Extraction complete — review below, then click Apply to populate the form.
            </span>
          )}
        </div>

        {/* Extraction draft preview */}
        {extractDraft && (
          <div className="mt-4 border rounded p-3 bg-white space-y-2">
            <p className="text-xs font-medium text-gray-600 mb-2">Extracted draft:</p>
            {extractDraft.brand_name && <p className="text-sm"><span className="text-xs text-gray-500">Brand name: </span>{extractDraft.brand_name}</p>}
            {extractDraft.positioning && <p className="text-sm"><span className="text-xs text-gray-500">Positioning: </span>{extractDraft.positioning}</p>}
            {!!extractDraft.personality?.length && <p className="text-sm"><span className="text-xs text-gray-500">Personality: </span>{extractDraft.personality.join(", ")}</p>}
            {extractDraft.target_audience && <p className="text-sm"><span className="text-xs text-gray-500">Audience: </span>{extractDraft.target_audience}</p>}
            {!!extractDraft.tone_principles?.length && <p className="text-sm"><span className="text-xs text-gray-500">Tone: </span>{extractDraft.tone_principles.join(" · ")}</p>}
            {!!extractDraft.forbidden_directions?.length && <p className="text-sm"><span className="text-xs text-gray-500">Forbidden: </span>{extractDraft.forbidden_directions.join(" · ")}</p>}
            {!!extractDraft.key_messages?.length && <p className="text-sm"><span className="text-xs text-gray-500">Key messages: </span>{extractDraft.key_messages.join(" · ")}</p>}
            <div className="flex gap-2 mt-3">
              <button
                type="button"
                onClick={applyDraft}
                className="px-3 py-1 bg-blue-600 text-white rounded text-xs"
              >
                Apply to form
              </button>
              <button
                type="button"
                onClick={() => setExtractDraft(null)}
                className="px-3 py-1 border rounded text-xs text-gray-600"
              >
                Discard
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Profile form */}
      <div className="space-y-5">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-xs text-gray-500 block mb-1">Brand name</label>
            <input
              type="text"
              value={profile.brand_name || ""}
              onChange={(e) => set("brand_name", e.target.value)}
              className="w-full border rounded px-2 py-1 text-sm"
            />
          </div>
        </div>

        <div>
          <label className="text-xs text-gray-500 block mb-1">Positioning <span className="text-gray-400">(what the brand stands for, for whom, vs whom)</span></label>
          <textarea
            value={profile.positioning || ""}
            onChange={(e) => set("positioning", e.target.value)}
            className="w-full border rounded px-2 py-1 text-sm min-h-[60px] resize-y"
          />
        </div>

        <div>
          <label className="text-xs text-gray-500 block mb-1">Target audience</label>
          <textarea
            value={profile.target_audience || ""}
            onChange={(e) => set("target_audience", e.target.value)}
            className="w-full border rounded px-2 py-1 text-sm min-h-[50px] resize-y"
          />
        </div>

        <div>
          <label className="text-xs text-gray-500 block mb-1">Competitive position <span className="text-gray-400">(how they differentiate)</span></label>
          <textarea
            value={profile.competitive_position || ""}
            onChange={(e) => set("competitive_position", e.target.value)}
            className="w-full border rounded px-2 py-1 text-sm min-h-[50px] resize-y"
          />
        </div>

        <ListInput
          label="Brand personality"
          hint="(e.g. 权威, 亲民, 专业)"
          items={profile.personality}
          onChange={(v) => set("personality", v)}
          placeholder="e.g. 权威"
        />

        <ListInput
          label="Tone principles"
          hint="(rules for how to communicate)"
          items={profile.tone_principles}
          onChange={(v) => set("tone_principles", v)}
          placeholder="e.g. 避免娱乐化表达"
        />

        <ListInput
          label="Forbidden directions"
          hint="(what to never do in strategy or copy)"
          items={profile.forbidden_directions}
          onChange={(v) => set("forbidden_directions", v)}
          placeholder="e.g. 不用竞品名字对比"
        />

        <ListInput
          label="Key messages"
          hint="(core points the brand wants to convey)"
          items={profile.key_messages}
          onChange={(v) => set("key_messages", v)}
          placeholder="e.g. 专业运动装备首选"
        />

        {/* Read-only: populated from feedback loop */}
        {(profile.approved_directions.length > 0 || profile.rejected_directions.length > 0) && (
          <div className="border-t pt-4 space-y-4">
            <p className="text-xs text-gray-400">The following are accumulated from client feedback — edit via project feedback, not here.</p>
            <ListInput label="Approved directions (from feedback)" items={profile.approved_directions} readonly />
            <ListInput label="Rejected directions (from feedback)" items={profile.rejected_directions} readonly />
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
          {saving ? "Saving..." : "Save Brand Profile"}
        </button>
        {saved && <span className="text-green-600 text-sm">Saved ✓</span>}
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ClientDetailPage() {
  const { clientId } = useParams<{ clientId: string }>();
  const [tab, setTab] = useState<"projects" | "brand-profile">("projects");

  return (
    <div className="max-w-4xl mx-auto p-8">
      <div className="flex items-center gap-2 mb-6">
        <Link href="/clients" className="text-blue-600 text-sm hover:underline">
          Clients
        </Link>
        <span className="text-gray-400">/</span>
        <h1 className="text-2xl font-bold">Client</h1>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b mb-6">
        {(["projects", "brand-profile"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-800"
            }`}
          >
            {t === "projects" ? "Projects" : "Brand Profile"}
          </button>
        ))}
      </div>

      {tab === "projects" && <ProjectsTab clientId={clientId} />}
      {tab === "brand-profile" && <BrandProfileTab clientId={clientId} />}
    </div>
  );
}
