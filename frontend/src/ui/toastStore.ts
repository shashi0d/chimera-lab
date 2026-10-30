import { create } from "zustand";

export type ToastKind = "info" | "success" | "warning" | "error";

export interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
  action?: { label: string; run: () => void };
  timeoutMs: number;
}

interface ToastState {
  toasts: Toast[];
  push(t: Omit<Toast, "id" | "timeoutMs"> & { timeoutMs?: number }): number;
  dismiss(id: number): void;
}

let nextId = 1;

export const useToasts = create<ToastState>()((set) => ({
  toasts: [],
  push(t) {
    const id = nextId++;
    const toast: Toast = { timeoutMs: t.kind === "error" ? 8000 : 5000, ...t, id };
    set((s) => ({ toasts: [...s.toasts.filter((x) => x.message !== toast.message), toast].slice(-4) }));
    return id;
  },
  dismiss(id) {
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
  },
}));

export const toast = {
  info: (message: string) => useToasts.getState().push({ kind: "info", message }),
  success: (message: string) => useToasts.getState().push({ kind: "success", message }),
  warning: (message: string) => useToasts.getState().push({ kind: "warning", message }),
  error: (message: string, action?: Toast["action"]) => useToasts.getState().push({ kind: "error", message, action }),
};
