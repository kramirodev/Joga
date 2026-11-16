import type { ReactNode } from "react";

import { AlertIcon, InfoIcon, RefreshIcon } from "./ui/Icons";

export function LoadingBlock({ label = "Carregando..." }: { label?: string }) {
  return (
    <div className="state-block" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <p>{label}</p>
    </div>
  );
}

export function SkeletonList({
  rows = 3,
  label = "Carregando...",
}: {
  rows?: number;
  label?: string;
}) {
  return (
    <div className="skeleton-list" role="status" aria-live="polite">
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="skeleton-row">
          <span className="skeleton skeleton--line skeleton--title" />
          <span className="skeleton skeleton--line" />
          <span className="skeleton skeleton--line skeleton--short" />
        </div>
      ))}
    </div>
  );
}

export function InlineSpinner({ label = "Processando" }: { label?: string }) {
  return (
    <span className="inline-spinner" role="status">
      <span className="spinner spinner--small" aria-hidden="true" />
      <span className="sr-only">{label}</span>
    </span>
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
      <span className="notice__icon" aria-hidden="true">
        <AlertIcon size={19} />
      </span>
      <div className="notice__body">
        <p>{message}</p>
        {requestId ? (
          <p className="notice__reference">
            Referência para suporte: <code>{requestId}</code>
          </p>
        ) : null}
      </div>
      {onRetry ? (
        <button type="button" className="button button--small button--ghost" onClick={onRetry}>
          <RefreshIcon size={15} />
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

export function InfoNotice({ children }: { children: ReactNode }) {
  return (
    <div className="notice notice--info">
      <span className="notice__icon" aria-hidden="true">
        <InfoIcon size={19} />
      </span>
      <div className="notice__body">{children}</div>
    </div>
  );
}

export function EmptyState({
  title,
  children,
  action,
  icon,
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="state-block state-block--empty">
      {icon ? (
        <span className="state-block__icon" aria-hidden="true">
          {icon}
        </span>
      ) : null}
      <h3>{title}</h3>
      {children ? <p>{children}</p> : null}
      {action ? <div className="state-block__action">{action}</div> : null}
    </div>
  );
}
