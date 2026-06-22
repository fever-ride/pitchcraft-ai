import { createSlice, createAsyncThunk, PayloadAction } from "@reduxjs/toolkit";
import { apiFetch } from "@/lib/api";

export interface Resource {
  _id: string;
  name: string;
  type: string;
  scope?: "shared" | "client";
  platforms?: Array<{
    name: string;
    followers_raw?: string;
    followers_count?: number;
    profile_url?: string;
  }>;
  primary_platform?: string;
  total_followers_count?: number;
  tags?: string[];
  pricing?: string;
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
  scope: "shared" | "client";
  clientId: string;
  typeFilter: string;
}

const initialState: ResourcesState = {
  resources: [],
  loading: false,
  importing: false,
  importResult: null,
  error: null,
  scope: "shared",
  clientId: "",
  typeFilter: "",
};

export const fetchResources = createAsyncThunk(
  "resources/fetchResources",
  async ({
    scope,
    clientId,
    typeFilter,
  }: {
    scope: "shared" | "client";
    clientId: string;
    typeFilter: string;
  }) => {
    if (scope === "client" && !clientId) return [];
    const params = new URLSearchParams({ scope });
    if (scope === "client" && clientId) params.set("client_id", clientId);
    if (typeFilter) params.set("type", typeFilter);
    const res = await apiFetch(`/api/v1/resources?${params}`);
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Request failed: ${res.status}`);
    }
    return res.json() as Promise<Resource[]>;
  }
);

export const importExcel = createAsyncThunk(
  "resources/importExcel",
  async ({
    file,
    scope,
    clientId,
  }: {
    file: File;
    scope: "shared" | "client";
    clientId: string;
  }) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("scope", scope);
    if (scope === "client" && clientId) {
      formData.append("client_id", clientId);
    }
    const res = await apiFetch("/api/v1/resources/import", {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || "Import failed");
    }
    const data = await res.json();
    return data.imported || 0;
  }
);

const resourcesSlice = createSlice({
  name: "resources",
  initialState,
  reducers: {
    setScope(state, action: PayloadAction<"shared" | "client">) {
      state.scope = action.payload;
      state.resources = [];
      state.error = null;
    },
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
        state.error = null;
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

export const { setScope, setClientId, setTypeFilter, clearImportResult } = resourcesSlice.actions;

export default resourcesSlice.reducer;
