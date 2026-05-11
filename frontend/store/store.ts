import { configureStore } from "@reduxjs/toolkit";
import campaignsReducer from "./campaignsSlice";
import pipelineReducer from "./pipelineSlice";

export const store = configureStore({
  reducer: {
    pipeline: pipelineReducer,
    campaigns: campaignsReducer,
  },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
