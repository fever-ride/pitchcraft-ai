"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Project {
  _id: string;
  name: string;
  status: string;
  created_at: string;
}

export default function ClientDetailPage() {
  const { clientId } = useParams<{ clientId: string }>();
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectName, setProjectName] = useState("");
  const [creating, setCreating] = useState(false);

  const headers = () => ({
    "Content-Type": "application/json",
    Authorization: `Bearer ${localStorage.getItem("token")}`,
  });

  const loadProjects = async () => {
    try {
      const data = await fetch(
        `${API_BASE}/api/v1/projects?client_id=${clientId}`,
        { headers: headers() }
      ).then((r) => r.json());
      setProjects(data);
    } catch {}
  };

  useEffect(() => {
    loadProjects();
  }, [clientId]);

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
    <div className="max-w-4xl mx-auto p-8">
      <div className="flex items-center gap-2 mb-6">
        <Link href="/clients" className="text-blue-600 text-sm hover:underline">
          Clients
        </Link>
        <span className="text-gray-400">/</span>
        <h1 className="text-2xl font-bold">Projects</h1>
      </div>

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
