import { configureStore } from "@reduxjs/toolkit";
import campaignsReducer from "./campaignsSlice";
import pipelineReducer from "./pipelineSlice";
import resourcesReducer from "./resourcesSlice";
import toastReducer from "./toastSlice";

export const store = configureStore({
  reducer: {
    pipeline: pipelineReducer,
    campaigns: campaignsReducer,
    resources: resourcesReducer,
    toast: toastReducer,
  },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
