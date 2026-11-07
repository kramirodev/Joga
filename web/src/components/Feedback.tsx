import type { ReactNode } from "react";

export function LoadingBlock({ label = "Carregando..." }: { label?: string }) {
  return (
    <div className="state-block" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <p>{label}</p>
    </div>
  );
}

export function ErrorNotice({
  message,
  requestId,
  onRetry,
}: {
  message: string;
  requestId?: string | null;
  onRetry?: () => void;
}) {
  return (
    <div className="notice notice--error" role="alert">
      <div className="notice__body">
        <p>{message}</p>
        {requestId ? (
          <p className="notice__reference">
            Referência para suporte: <code>{requestId}</code>
          </p>
        ) : null}
      </div>
      {onRetry ? (
        <button type="button" className="button button--small" onClick={onRetry}>
          Tentar novamente
        </button>
      ) : null}
    </div>
  );
}

export function SuccessNotice({ children }: { children: ReactNode }) {
  return (
    <div className="notice notice--success" role="status" aria-live="polite">
      {children}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="state-block state-block--empty">
      <h3>{title}</h3>
      {children ? <p>{children}</p> : null}
    </div>
  );
}
