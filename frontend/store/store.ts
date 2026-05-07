import { configureStore } from "@reduxjs/toolkit";
import pipelineReducer from "./pipelineSlice";

export const store = configureStore({
  reducer: {
    pipeline: pipelineReducer,
  },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
