import { ApiError } from "./api";
import { requestIdOf } from "./format";

export const CLIENT_EVENTS_PATH = "/api/v1/observability/client-events";

export type ClientErrorLevel = "warn" | "error" | "fatal";

export interface ClientErrorContext {
  componentStack?: string | null;
  source?: string;
  module?: string;
  screen?: string;
  requestId?: string | null;
  correlationId?: string | null;
  errorCode?: string;
  level?: ClientErrorLevel;
}

export interface ClientErrorEvent {
  level: ClientErrorLevel;
  message: string;
  stack?: string;
  error_code?: string;
  module: string;
  platform: "web";
  app_version: string;
  screen: string;
  request_id?: string;
  correlation_id?: string;
}

const APP_VERSION = import.meta.env.VITE_APP_VERSION ?? "0.1.0";
const MESSAGE_LIMIT = 500;
const STACK_LIMIT = 4000;
const DEDUPE_WINDOW_MS = 60_000;
const SESSION_SEND_LIMIT = 20;

const IGNORED_MESSAGES = [
  "ResizeObserver loop limit exceeded",
  "ResizeObserver loop completed with undelivered notifications",
];

const MASK_TOKEN = "[removido]";

const EMAIL_PATTERN = /[\w.+-]+@[\w-]+(?:\.[\w-]+)+/g;
const CPF_PATTERN = /\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b/g;
const PHONE_PATTERN = /(?:\+?55[\s-]?)?\(?\d{2}\)?[\s-]?9?\d{4}[\s-]?\d{4}\b/g;
const BEARER_PATTERN = /\bBearer\s+[A-Za-z0-9._~+/=-]+/gi;
const JWT_PATTERN = /\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b/g;
const SECRET_PATTERN =
  /\b(password|senha|token|access_token|refresh_token|secret|api[_-]?key)\s*[=:]\s*[^\s&,;"']+/gi;

const recentKeys = new Map<string, number>();
let sessionSends = 0;

/** Limpa o estado interno. Usado apenas em testes. */
export function resetTelemetryForTests(): void {
  recentKeys.clear();
  sessionSends = 0;
}

function maskText(value: string): string {
  return value
    .replace(BEARER_PATTERN, `Bearer ${MASK_TOKEN}`)
    .replace(JWT_PATTERN, MASK_TOKEN)
    .replace(SECRET_PATTERN, (_match, key: string) => `${key}=${MASK_TOKEN}`)
    .replace(EMAIL_PATTERN, "[email]")
    .replace(CPF_PATTERN, "[documento]")
    .replace(PHONE_PATTERN, "[telefone]");
}

function truncate(value: string, limit: number): string {
  return value.length <= limit ? value : `${value.slice(0, limit - 1)}…`;
}

function screenPath(value: string): string {
  const path = value.split("#")[0].split("?")[0].trim();
  return path.startsWith("/") ? path : "/";
}

function safeId(value: string | null | undefined): string | undefined {
  const trimmed = value?.trim();
  if (!trimmed) return undefined;
  return /^[A-Za-z0-9._:-]{1,64}$/.test(trimmed) ? trimmed : undefined;
}

interface ErrorDescription {
  message: string;
  stack?: string;
  errorCode?: string;
}

function describeError(error: unknown): ErrorDescription {
  if (error instanceof Error) {
    const code = (error as Error & { code?: unknown }).code;
    return {
      message: error.message || error.name || "Erro sem descrição",
      stack: error.stack,
      errorCode: typeof code === "string" ? code : undefined,
    };
  }
  if (typeof error === "string") return { message: error };
  try {
    return { message: String(error) };
  } catch {
    return { message: "Erro sem descrição" };
  }
}

export function isIgnorableError(error: unknown): boolean {
  const description = describeError(error);
  if (description.message.includes("ResizeObserver loop")) return true;
  if (IGNORED_MESSAGES.some((text) => description.message.includes(text))) return true;
  if (error instanceof Error && error.name === "AbortError") return true;
  return /\babort(error|ed)?\b/i.test(description.message);
}

function isDuplicate(key: string, now: number): boolean {
  const seenAt = recentKeys.get(key);
  if (seenAt !== undefined && now - seenAt < DEDUPE_WINDOW_MS) return true;
  for (const [storedKey, storedAt] of recentKeys) {
    if (now - storedAt >= DEDUPE_WINDOW_MS) recentKeys.delete(storedKey);
  }
  recentKeys.set(key, now);
  return false;
}

function sendEvent(event: ClientErrorEvent): void {
  if (typeof fetch !== "function") return;
  try {
    const request = fetch(CLIENT_EVENTS_PATH, {
      method: "POST",
      credentials: "same-origin",
      keepalive: true,
      headers: { "Content-Type": "application/json", "X-Client": "web" },
      body: JSON.stringify({ events: [event] }),
    });
    // A falha de envio é silenciosa: nunca vira erro não tratado nem laço.
    if (request && typeof request.catch === "function") request.catch(() => undefined);
  } catch {
    // Silencioso por projeto: relatar erro nunca pode quebrar o painel.
  }
}

export function buildClientErrorEvent(
  error: unknown,
  context: ClientErrorContext = {},
): ClientErrorEvent | null {
  const details = describeError(error);
  const message = truncate(maskText(details.message), MESSAGE_LIMIT).trim();
  if (!message) return null;

  const stackParts = [details.stack, context.componentStack].filter(
    (part): part is string => typeof part === "string" && part.trim().length > 0,
  );
  const stack = stackParts.length
    ? truncate(maskText(stackParts.join("\n")), STACK_LIMIT)
    : undefined;

  const event: ClientErrorEvent = {
    level: context.level ?? "error",
    message,
    module: context.module ?? context.source ?? "panel",
    platform: "web",
    app_version: APP_VERSION,
    screen: screenPath(context.screen ?? window.location.pathname),
  };

  if (stack) event.stack = stack;

  const errorCode =
    context.errorCode ?? (error instanceof ApiError ? error.code : details.errorCode);
  if (errorCode) event.error_code = truncate(maskText(errorCode), 100);

  const requestId = safeId(context.requestId ?? requestIdOf(error));
  if (requestId) event.request_id = requestId;

  const correlationId = safeId(context.correlationId);
  if (correlationId) event.correlation_id = correlationId;

  return event;
}

export function reportClientError(error: unknown, context: ClientErrorContext = {}): void {
  try {
    if (typeof window === "undefined") return;
    const event = buildClientErrorEvent(error, context);
    if (!event) return;

    const now = Date.now();
    if (isDuplicate(`${event.screen}::${event.message}`, now)) return;
    if (sessionSends >= SESSION_SEND_LIMIT) return;

    sessionSends += 1;
    sendEvent(event);
  } catch {
    // Relatar erro nunca pode quebrar o painel.
  }
}

export function handleGlobalError(event: ErrorEvent): void {
  const candidate = event.error ?? event.message;
  if (isIgnorableError(candidate)) return;
  reportClientError(candidate, { source: "window.error" });
}

export function handleUnhandledRejection(event: PromiseRejectionEvent): void {
  if (isIgnorableError(event.reason)) return;
  reportClientError(event.reason, { source: "unhandledrejection" });
}

let installed = false;

export function installGlobalErrorReporting(): void {
  if (installed || typeof window === "undefined") return;
  if (!import.meta.env.PROD) return;
  installed = true;
  window.addEventListener("error", handleGlobalError);
  window.addEventListener("unhandledrejection", handleUnhandledRejection);
}
