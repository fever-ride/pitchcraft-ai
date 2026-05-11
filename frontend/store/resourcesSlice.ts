import { createSlice, createAsyncThunk, PayloadAction } from "@reduxjs/toolkit";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken(): string | null {
  return typeof window !== "undefined" ? localStorage.getItem("token") : null;
}

async function fetchJson<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export interface Resource {
  _id: string;
  name: string;
  type: string;
  platform?: string;
  tags?: string[];
  pricing?: string;
  followers?: string;
  outlet_type?: string;
  service_type?: string;
  placement_type?: string;
}

interface ResourcesState {
  resources: Resource[];
  loading: boolean;
  importing: boolean;
  importResult: string | null;
  error: string | null;
  clientId: string;
  typeFilter: string;
}

const initialState: ResourcesState = {
  resources: [],
  loading: false,
  importing: false,
  importResult: null,
  error: null,
  clientId: "",
  typeFilter: "",
};

export const fetchResources = createAsyncThunk(
  "resources/fetchResources",
  async ({ clientId, typeFilter }: { clientId: string; typeFilter: string }) => {
    if (!clientId) return [];
    const params = new URLSearchParams({ client_id: clientId });
    if (typeFilter) params.set("type", typeFilter);
    return fetchJson<Resource[]>(`/api/v1/resources?${params}`);
  }
);

export const importExcel = createAsyncThunk(
  "resources/importExcel",
  async ({ file, clientId }: { file: File; clientId: string }) => {
    const token = getToken();
    const formData = new FormData();
    formData.append("file", file);
    formData.append("client_id", clientId);
    const res = await fetch(`${API_BASE}/api/v1/resources/import`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    });
    if (!res.ok) throw new Error("Import failed");
    const data = await res.json();
    return data.imported || 0;
  }
);

const resourcesSlice = createSlice({
  name: "resources",
  initialState,
  reducers: {
    setClientId(state, action: PayloadAction<string>) {
      state.clientId = action.payload;
    },
    setTypeFilter(state, action: PayloadAction<string>) {
      state.typeFilter = action.payload;
    },
    clearImportResult(state) {
      state.importResult = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchResources.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchResources.fulfilled, (state, action) => {
        state.loading = false;
        state.resources = action.payload;
      })
      .addCase(fetchResources.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message || "Failed to load resources";
      })
      .addCase(importExcel.pending, (state) => {
        state.importing = true;
        state.importResult = null;
      })
      .addCase(importExcel.fulfilled, (state, action) => {
        state.importing = false;
        state.importResult = `Imported ${action.payload} resources`;
      })
      .addCase(importExcel.rejected, (state, action) => {
        state.importing = false;
        state.error = action.error.message || "Import failed";
      });
  },
});

export const { setClientId, setTypeFilter, clearImportResult } = resourcesSlice.actions;

export default resourcesSlice.reducer;
