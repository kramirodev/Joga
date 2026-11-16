import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { AlertIcon, CheckIcon, CloseIcon, InfoIcon } from "./Icons";
import { ToastContext, type ToastInput, type ToastTone } from "./toast-context";

interface ToastItem extends ToastInput {
  id: number;
  tone: ToastTone;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(1);
  const timers = useRef<Map<number, number>>(new Map());

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
    const timer = timers.current.get(id);
    if (timer) {
      window.clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  const push = useCallback(
    (toast: ToastInput) => {
      const id = nextId.current;
      nextId.current += 1;
      const item: ToastItem = { ...toast, id, tone: toast.tone ?? "success" };
      setToasts((current) => [...current.slice(-3), item]);
      const timeout = window.setTimeout(() => dismiss(id), item.tone === "error" ? 9000 : 5500);
      timers.current.set(id, timeout);
    },
    [dismiss],
  );

  useEffect(() => {
    const pending = timers.current;
    return () => {
      for (const timer of pending.values()) window.clearTimeout(timer);
      pending.clear();
    };
  }, []);

  const value = useMemo(() => ({ push, dismiss }), [push, dismiss]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-viewport" aria-live="polite" aria-relevant="additions">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`toast toast--${toast.tone}`}
            role={toast.tone === "error" ? "alert" : "status"}
          >
            <span className="toast__icon" aria-hidden="true">
              {toast.tone === "success" ? (
                <CheckIcon size={18} />
              ) : toast.tone === "error" ? (
                <AlertIcon size={18} />
              ) : (
                <InfoIcon size={18} />
              )}
            </span>
            <div className="toast__body">
              <p className="toast__title">{toast.title}</p>
              {toast.description ? <p className="toast__description">{toast.description}</p> : null}
              {toast.requestId ? (
                <p className="toast__reference">
                  Referência: <code>{toast.requestId}</code>
                </p>
              ) : null}
            </div>
            <button
              type="button"
              className="icon-button icon-button--small"
              aria-label="Fechar aviso"
              onClick={() => dismiss(toast.id)}
            >
              <CloseIcon size={15} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
