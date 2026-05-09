const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

let isRefreshing = false;
let refreshQueue: Array<() => void> = [];

function getToken(): string | null {
  return typeof window !== "undefined" ? localStorage.getItem("token") : null;
}

async function refreshToken(): Promise<boolean> {
  const refresh = typeof window !== "undefined" ? localStorage.getItem("refresh") : null;
  if (!refresh) return false;

  try {
    const res = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    localStorage.setItem("token", data.access_token);
    if (data.refresh_token) localStorage.setItem("refresh", data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ...headers, ...options?.headers },
  });

  if (res.status === 401 && token) {
    if (!isRefreshing) {
      isRefreshing = true;
      const refreshed = await refreshToken();
      isRefreshing = false;

      if (refreshed) {
        refreshQueue.forEach((cb) => cb());
        refreshQueue = [];
        return request<T>(path, options);
      } else {
        refreshQueue = [];
        localStorage.removeItem("token");
        localStorage.removeItem("refresh");
        if (typeof window !== "undefined") window.location.href = "/login";
        throw new Error("Session expired");
      }
    } else {
      return new Promise<T>((resolve) => {
        refreshQueue.push(() => resolve(request<T>(path, options)));
      });
    }
  }

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
