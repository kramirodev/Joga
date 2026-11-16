import { createContext, useContext } from "react";

export type ToastTone = "success" | "error" | "info";

export interface ToastInput {
  title: string;
  description?: string;
  tone?: ToastTone;
  requestId?: string | null;
}

export interface ToastApi {
  push: (toast: ToastInput) => void;
  dismiss: (id: number) => void;
}

export const ToastContext = createContext<ToastApi | null>(null);

const fallback: ToastApi = { push: () => undefined, dismiss: () => undefined };

export function useToast(): ToastApi {
  return useContext(ToastContext) ?? fallback;
}
