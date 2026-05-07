import { createSlice, PayloadAction } from "@reduxjs/toolkit";

interface Slide {
  index: number;
  content: Record<string, unknown>;
  status: "pending" | "confirmed" | "flagged";
  feedback?: string;
}

interface NarrativeSuggestion {
  page: number;
  issue: string;
}

interface PipelineState {
  pipelineId: string | null;
  status: "idle" | "running" | "paused" | "completed" | "error";
  currentNode: string | null;
  slides: Slide[];
  narrativeSuggestions: NarrativeSuggestion[];
  error: string | null;
}

const initialState: PipelineState = {
  pipelineId: null,
  status: "idle",
  currentNode: null,
  slides: [],
  narrativeSuggestions: [],
  error: null,
};

const pipelineSlice = createSlice({
  name: "pipeline",
  initialState,
  reducers: {
    setPipelineId(state, action: PayloadAction<string>) {
      state.pipelineId = action.payload;
      state.status = "running";
    },
    setCurrentNode(state, action: PayloadAction<string>) {
      state.currentNode = action.payload;
    },
    setPaused(state, action: PayloadAction<string>) {
      state.status = "paused";
      state.currentNode = action.payload;
    },
    addSlide(state, action: PayloadAction<Slide>) {
      state.slides.push(action.payload);
    },
    updateSlideStatus(
      state,
      action: PayloadAction<{ index: number; status: Slide["status"]; feedback?: string }>
    ) {
      const slide = state.slides.find((s) => s.index === action.payload.index);
      if (slide) {
        slide.status = action.payload.status;
        slide.feedback = action.payload.feedback;
      }
    },
    setNarrativeSuggestions(state, action: PayloadAction<NarrativeSuggestion[]>) {
      state.narrativeSuggestions = action.payload;
    },
    setCompleted(state, action: PayloadAction<string | undefined>) {
      state.status = "completed";
    },
    setError(state, action: PayloadAction<string>) {
      state.status = "error";
      state.error = action.payload;
    },
    reset() {
      return initialState;
    },
  },
});

export const {
  setPipelineId,
  setCurrentNode,
  setPaused,
  addSlide,
  updateSlideStatus,
  setNarrativeSuggestions,
  setCompleted,
  setError,
  reset,
} = pipelineSlice.actions;

export default pipelineSlice.reducer;
