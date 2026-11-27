import { ApiError } from "./api";
import { adminErrorMessage } from "./admin";
import type { ObservabilityEventFilters } from "../types";

export type ObservabilityWindow = "24h" | "7d";

export const OBSERVABILITY_WINDOWS: Array<{ value: ObservabilityWindow; label: string }> = [
  { value: "24h", label: "Últimas 24 horas" },
  { value: "7d", label: "Últimos 7 dias" },
];

export function observabilityWindow(value: string | null): ObservabilityWindow {
  return value === "7d" ? "7d" : "24h";
}

export const LEVEL_OPTIONS = [
  { value: "", label: "Todos os níveis" },
  { value: "debug", label: "Detalhe" },
  { value: "info", label: "Informação" },
  { value: "warn", label: "Aviso" },
  { value: "error", label: "Erro" },
  { value: "fatal", label: "Crítico" },
];

export const CATEGORY_OPTIONS = [
  { value: "", label: "Todas as categorias" },
  { value: "http", label: "Requisições" },
  { value: "app", label: "Aplicação" },
  { value: "security", label: "Segurança" },
  { value: "audit", label: "Auditoria" },
  { value: "job", label: "Tarefas" },
  { value: "client", label: "Aplicativo" },
];

const LEVEL_LABELS: Record<string, string> = {
  debug: "Detalhe",
  info: "Informação",
  warn: "Aviso",
  error: "Erro",
  fatal: "Crítico",
};

const CATEGORY_LABELS: Record<string, string> = {
  http: "Requisições",
  app: "Aplicação",
  security: "Segurança",
  audit: "Auditoria",
  job: "Tarefas",
  client: "Aplicativo",
};

const SOURCE_LABELS: Record<string, string> = {
  log_events: "Registro técnico",
  security_events: "Segurança",
  audit_logs: "Auditoria",
};

export function levelLabel(level: string): string {
  return LEVEL_LABELS[level] ?? level;
}

export function levelTone(level: string): string {
  switch (level) {
    case "error":
    case "fatal":
      return "danger";
    case "warn":
      return "warning";
    case "info":
      return "info";
    default:
      return "muted";
  }
}

export function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? category;
}

export function eventSourceLabel(source: string): string {
  return SOURCE_LABELS[source] ?? source;
}

export function statusTone(status: number | null): string {
  if (status === null) return "muted";
  if (status >= 500) return "danger";
  if (status >= 400) return "warning";
  return "success";
}

export function formatCount(value: number): string {
  return new Intl.NumberFormat("pt-BR").format(value);
}

const ALERT_LABELS: Record<string, string> = {
  login_failures: "Falhas de acesso",
  server_errors: "Erros do servidor",
  failed_jobs: "Tarefas com falha",
  client_errors: "Erros no aplicativo",
};

const ALERT_TARGETS: Record<string, string> = {
  login_failures: "/admin/observability/events?category=security",
  server_errors: "/admin/observability/events?level=error&category=http",
  failed_jobs: "/admin/observability/events?category=job&level=error",
  client_errors: "/admin/observability/events?category=client&level=error",
};

const ALERT_LEVEL_LABELS: Record<string, string> = {
  warning: "Atenção",
  critical: "Crítico",
};

export function alertLabel(code: string): string {
  return ALERT_LABELS[code] ?? "Alerta";
}

export function alertTarget(code: string): string {
  return ALERT_TARGETS[code] ?? "/admin/observability/events";
}

export function alertTone(level: string): string {
  return level === "critical" ? "danger" : "warning";
}

export function alertLevelLabel(level: string): string {
  return ALERT_LEVEL_LABELS[level] ?? level;
}

export function formatDuration(value: number | null): string {
  if (value === null) return "—";
  if (value < 1000) return `${formatCount(value)} ms`;
  const seconds = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(value / 1000);
  return `${seconds} s`;
}

export function requestRateText(part: number, requests: number): string {
  if (requests <= 0) return "sem requisições no período";
  const rate = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(
    (part / requests) * 100,
  );
  return `${rate}% das requisições`;
}

export interface EventFilterFormState {
  from: string;
  to: string;
  level: string;
  category: string;
  userId: string;
  ip: string;
  endpoint: string;
  status: string;
  requestId: string;
  correlationId: string;
  q: string;
}

export const EMPTY_EVENT_FILTERS: EventFilterFormState = {
  from: "",
  to: "",
  level: "",
  category: "",
  userId: "",
  ip: "",
  endpoint: "",
  status: "",
  requestId: "",
  correlationId: "",
  q: "",
};

export function readEventFilters(params: URLSearchParams): EventFilterFormState {
  return {
    from: params.get("from") ?? "",
    to: params.get("to") ?? "",
    level: params.get("level") ?? "",
    category: params.get("category") ?? "",
    userId: params.get("user_id") ?? "",
    ip: params.get("ip") ?? "",
    endpoint: params.get("endpoint") ?? "",
    status: params.get("status") ?? "",
    requestId: params.get("request_id") ?? "",
    correlationId: params.get("correlation_id") ?? "",
    q: params.get("q") ?? "",
  };
}

export function writeEventFilters(filters: EventFilterFormState): URLSearchParams {
  const params = new URLSearchParams();
  const entries: Array<[string, string]> = [
    ["from", filters.from],
    ["to", filters.to],
    ["level", filters.level],
    ["category", filters.category],
    ["user_id", filters.userId],
    ["ip", filters.ip],
    ["endpoint", filters.endpoint],
    ["status", filters.status],
    ["request_id", filters.requestId],
    ["correlation_id", filters.correlationId],
    ["q", filters.q],
  ];
  for (const [key, raw] of entries) {
    const value = raw.trim();
    if (value) params.set(key, value);
  }
  return params;
}

export function toApiFilters(filters: EventFilterFormState): ObservabilityEventFilters {
  const status = filters.status.trim();
  return {
    from: filters.from || undefined,
    to: filters.to || undefined,
    level: filters.level || undefined,
    category: filters.category || undefined,
    userId: filters.userId.trim() || undefined,
    ip: filters.ip.trim() || undefined,
    endpoint: filters.endpoint.trim() || undefined,
    status: /^\d{3}$/.test(status) ? Number(status) : undefined,
    requestId: filters.requestId.trim() || undefined,
    correlationId: filters.correlationId.trim() || undefined,
    q: filters.q.trim() || undefined,
  };
}

export function eventFilterKey(filters: ObservabilityEventFilters): string {
  return JSON.stringify(
    Object.entries(filters)
      .filter(([, value]) => value !== undefined && value !== null && value !== "")
      .sort(([left], [right]) => left.localeCompare(right)),
  );
}

export function isoToLocalInput(iso: string): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
}

export function localInputToIso(value: string): string {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toISOString();
}

export function variationText(current: number, previous: number): string {
  if (previous === 0) {
    return current === 0 ? "sem eventos nos dois períodos" : "sem base de comparação";
  }
  const change = Math.round(((current - previous) / previous) * 100);
  if (change === 0) return "estável em relação ao período anterior";
  return `${change > 0 ? "+" : ""}${formatCount(change)}% em relação ao período anterior`;
}

export async function copyToClipboard(value: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value);
      return true;
    }
  } catch {
    // Sem permissão para a área de transferência: tenta o recurso alternativo.
  }
  try {
    const area = document.createElement("textarea");
    area.value = value;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    const copied = document.execCommand("copy");
    document.body.removeChild(area);
    return copied;
  } catch {
    return false;
  }
}

const OBSERVABILITY_ERRORS: Record<string, string> = {
  invalid_ip: "Informe um endereço IP válido.",
  invalid_time_range: "A data inicial não pode ser posterior à data final.",
  invalid_cursor: "A paginação expirou. Recomece a partir da primeira página.",
  invalid_window: "Escolha um período de 24 horas ou 7 dias.",
  invalid_level: "O nível escolhido não é reconhecido.",
  invalid_category: "A categoria escolhida não é reconhecida.",
  event_not_found: "Este evento não foi encontrado. Ele pode ter saído do período de retenção.",
};

export function observabilityErrorMessage(error: unknown): string {
  if (error instanceof ApiError && OBSERVABILITY_ERRORS[error.code]) {
    return OBSERVABILITY_ERRORS[error.code];
  }
  return adminErrorMessage(error);
}

export function observabilityPollInterval(): number | false {
  if (typeof document !== "undefined" && document.hidden) return false;
  return 30_000;
}
