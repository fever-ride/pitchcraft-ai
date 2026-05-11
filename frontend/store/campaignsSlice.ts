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
      "Content-Type": "application/json",
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

// --- Types ---

export interface CampaignMeta {
  campaign_type?: string;
  industry?: string;
  budget_tier?: string;
  target_audience_summary?: string;
  duration_days?: number;
  channels_used?: string[];
  client_id?: string;
}

export interface CampaignRecord {
  id: string;
  status: string;
  confidence: string;
  client_id?: string;
  project_id?: string;
  created_at?: string;
  confirmed_at?: string;
  meta?: CampaignMeta;
  strategy_decisions?: Record<string, unknown>;
  communication_plan?: Record<string, unknown>;
  media_plan?: Record<string, unknown>;
  execution?: Record<string, unknown>;
  outcome?: Record<string, unknown>;
  client_learnings?: Record<string, unknown>;
  deck_info?: Record<string, unknown>;
}

interface CampaignsState {
  records: CampaignRecord[];
  currentRecord: CampaignRecord | null;
  edits: Record<string, unknown>;
  loading: boolean;
  confirming: boolean;
  error: string | null;
  tab: "pending" | "all";
  clientFilter: string;
}

const initialState: CampaignsState = {
  records: [],
  currentRecord: null,
  edits: {},
  loading: false,
  confirming: false,
  error: null,
  tab: "pending",
  clientFilter: "",
};

// --- Thunks ---

export const fetchRecords = createAsyncThunk(
  "campaigns/fetchRecords",
  async ({ tab, clientId }: { tab: "pending" | "all"; clientId?: string }) => {
    const endpoint = tab === "pending" ? "/api/v1/campaigns/pending" : "/api/v1/campaigns";
    const params = new URLSearchParams();
    if (clientId) params.set("client_id", clientId);
    return fetchJson<CampaignRecord[]>(`${endpoint}?${params}`);
  }
);

export const fetchRecord = createAsyncThunk(
  "campaigns/fetchRecord",
  async (recordId: string) => {
    return fetchJson<CampaignRecord>(`/api/v1/campaigns/${recordId}`);
  }
);

export const confirmRecord = createAsyncThunk(
  "campaigns/confirmRecord",
  async ({ recordId, edits }: { recordId: string; edits: Record<string, unknown> }) => {
    // Convert flat edits (meta.industry -> value) to nested structure
    const nestedEdits: Record<string, Record<string, unknown>> = {};
    for (const [key, value] of Object.entries(edits)) {
      const [module, field] = key.split(".");
      if (!nestedEdits[module]) nestedEdits[module] = {};
      nestedEdits[module][field] = value;
    }
    return fetchJson<{ record_id: string; status: string }>(
      `/api/v1/campaigns/${recordId}/confirm`,
      { method: "PUT", body: JSON.stringify({ edits: nestedEdits }) }
    );
  }
);

// --- Slice ---

const campaignsSlice = createSlice({
  name: "campaigns",
  initialState,
  reducers: {
    setTab(state, action: PayloadAction<"pending" | "all">) {
      state.tab = action.payload;
    },
    setClientFilter(state, action: PayloadAction<string>) {
      state.clientFilter = action.payload;
    },
    setEdit(state, action: PayloadAction<{ key: string; value: unknown }>) {
      state.edits[action.payload.key] = action.payload.value;
    },
    clearEdits(state) {
      state.edits = {};
    },
    clearCurrentRecord(state) {
      state.currentRecord = null;
      state.edits = {};
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchRecords.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchRecords.fulfilled, (state, action) => {
        state.loading = false;
        state.records = action.payload;
      })
      .addCase(fetchRecords.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message || "Failed to load records";
      })
      .addCase(fetchRecord.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchRecord.fulfilled, (state, action) => {
        state.loading = false;
        state.currentRecord = action.payload;
      })
      .addCase(fetchRecord.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message || "Record not found";
      })
      .addCase(confirmRecord.pending, (state) => {
        state.confirming = true;
        state.error = null;
      })
      .addCase(confirmRecord.fulfilled, (state) => {
        state.confirming = false;
        state.edits = {};
        if (state.currentRecord) {
          state.currentRecord.status = "confirmed";
        }
      })
      .addCase(confirmRecord.rejected, (state, action) => {
        state.confirming = false;
        state.error = action.error.message || "Confirmation failed";
      });
  },
});

export const { setTab, setClientFilter, setEdit, clearEdits, clearCurrentRecord } =
  campaignsSlice.actions;

export default campaignsSlice.reducer;
