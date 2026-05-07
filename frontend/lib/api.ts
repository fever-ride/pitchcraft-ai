// TODO: add token refresh interceptor — on 401, call /api/v1/auth/refresh then retry
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ...headers, ...options?.headers },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }

  return res.json();
}

export const api = {
  startPipeline(data: { project_id: string; client_id: string; raw_brief: string }) {
    return request<{ pipeline_id: string; status: string }>("/api/v1/pipeline/start", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  confirmNode(pipelineId: string, data: { node: string; action: string; feedback?: string; edits?: Record<string, unknown> }) {
    return request<{ status: string }>(`/api/v1/pipeline/${pipelineId}/confirm`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  getPipelineStatus(pipelineId: string) {
    return request<Record<string, unknown>>(`/api/v1/pipeline/${pipelineId}/status`);
  },

  getBrief(pipelineId: string) {
    return request<{ structured_brief: Record<string, unknown>; raw_brief: string }>(`/api/v1/pipeline/${pipelineId}/brief`);
  },

  getStrategy(pipelineId: string) {
    return request<Record<string, unknown>>(`/api/v1/pipeline/${pipelineId}/strategy`);
  },

  getSlides(pipelineId: string) {
    return request<{ slides: unknown[]; narrative_suggestions: unknown[]; deck_structure: unknown[] }>(`/api/v1/pipeline/${pipelineId}/slides`);
  },

  uploadFile(formData: FormData) {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    return fetch(`${API_BASE}/api/v1/files/upload`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    }).then((res) => res.json());
  },

  listFiles(clientId?: string, projectId?: string) {
    const params = new URLSearchParams();
    if (clientId) params.set("client_id", clientId);
    if (projectId) params.set("project_id", projectId);
    return request<unknown[]>(`/api/v1/files?${params}`);
  },
};
