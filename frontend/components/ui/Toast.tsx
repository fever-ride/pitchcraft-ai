"use client";

import { useEffect } from "react";
import { useDispatch, useSelector } from "react-redux";

import type { AppDispatch, RootState } from "@/store/store";
import { removeToast } from "@/store/toastSlice";

const COLORS = {
  success: "bg-green-600",
  error: "bg-red-600",
  info: "bg-blue-600",
};

export function ToastContainer() {
  const dispatch = useDispatch<AppDispatch>();
  const { toasts } = useSelector((state: RootState) => state.toast);

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => (
        <ToastItem
          key={toast.id}
          id={toast.id}
          message={toast.message}
          type={toast.type}
          onDismiss={() => dispatch(removeToast(toast.id))}
        />
      ))}
    </div>
  );
}

function ToastItem({
  id,
  message,
  type,
  onDismiss,
}: {
  id: string;
  message: string;
  type: "success" | "error" | "info";
  onDismiss: () => void;
}) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, 3000);
    return () => clearTimeout(timer);
  }, [id, onDismiss]);

  return (
    <div className={`${COLORS[type]} text-white px-4 py-2 rounded shadow-lg text-sm flex items-center gap-2 min-w-[200px]`}>
      <span className="flex-1">{message}</span>
      <button onClick={onDismiss} className="text-white/70 hover:text-white">
        &times;
      </button>
    </div>
  );
}
