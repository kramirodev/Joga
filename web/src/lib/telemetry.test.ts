import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "./api";
import {
  CLIENT_EVENTS_PATH,
  handleGlobalError,
  handleUnhandledRejection,
  reportClientError,
  resetTelemetryForTests,
  type ClientErrorEvent,
} from "./telemetry";

type FetchMock = ReturnType<typeof vi.fn>;

function stubFetch(impl?: () => Promise<Response>): FetchMock {
  const fetchMock = vi.fn(impl ?? (async () => new Response(null, { status: 202 })));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function sentEvents(fetchMock: FetchMock): ClientErrorEvent[] {
  return fetchMock.mock.calls.map(([, init]) => {
    const body = JSON.parse(String((init as RequestInit).body)) as { events: ClientErrorEvent[] };
    return body.events[0]!;
  });
}

describe("telemetria do painel", () => {
  beforeEach(() => {
    resetTelemetryForTests();
    window.history.replaceState({}, "", "/");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("envia o payload esperado sem query nem fragmento na tela", () => {
    window.history.replaceState({}, "", "/admin/observability/events?level=error&q=segredo#topo");
    const fetchMock = stubFetch();

    reportClientError(new Error("Falha ao carregar a lista"), { module: "panel" });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(path).toBe(CLIENT_EVENTS_PATH);
    expect(init.method).toBe("POST");
    expect(init.keepalive).toBe(true);
    expect(init.credentials).toBe("same-origin");
    expect((init.headers as Record<string, string>)["X-Client"]).toBe("web");

    const [event] = sentEvents(fetchMock);
    expect(event).toMatchObject({
      level: "error",
      message: "Falha ao carregar a lista",
      module: "panel",
      platform: "web",
      app_version: "0.1.0",
      screen: "/admin/observability/events",
    });
    expect(JSON.stringify(init.body)).not.toContain("segredo");
    expect(event.stack).toContain("Falha ao carregar a lista");
  });

  it("mascara e-mail, telefone, documento e tokens antes de enviar", () => {
    const fetchMock = stubFetch();
    const jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc123";
    const message =
      `Falha para ana@example.com, telefone (11) 98765-4321, CPF 123.456.789-09, ` +
      `Authorization: Bearer ${jwt}, password=segredo123`;

    reportClientError(new Error(message));

    const [event] = sentEvents(fetchMock);
    expect(event.message).toContain("[email]");
    expect(event.message).toContain("[telefone]");
    expect(event.message).toContain("[documento]");
    expect(event.message).toContain("[removido]");
    expect(event.message).not.toContain("ana@example.com");
    expect(event.message).not.toContain("98765-4321");
    expect(event.message).not.toContain("123.456.789-09");
    expect(event.message).not.toContain(jwt);
    expect(event.message).not.toContain("segredo123");
  });

  it("trunca mensagem e rastreamento muito longos", () => {
    const fetchMock = stubFetch();
    const error = new Error("a".repeat(2000));
    error.stack = "b".repeat(9000);

    reportClientError(error);

    const [event] = sentEvents(fetchMock);
    expect(event.message.length).toBeLessThanOrEqual(500);
    expect(event.message.endsWith("…")).toBe(true);
    expect(event.stack?.length).toBeLessThanOrEqual(4000);
  });

  it("usa o identificador da requisição e o código quando o erro vem da API", () => {
    const fetchMock = stubFetch();

    reportClientError(new ApiError(500, "server_error", "Falha no servidor", "req-123"));

    const [event] = sentEvents(fetchMock);
    expect(event.error_code).toBe("server_error");
    expect(event.request_id).toBe("req-123");
    expect(event.message).toBe("Falha no servidor");
  });

  it("inclui o empilhamento de componentes no rastreamento", () => {
    const fetchMock = stubFetch();

    reportClientError(new Error("Falha de renderização"), {
      componentStack: "\n    at PainelAdmin",
      source: "error-boundary",
    });

    const [event] = sentEvents(fetchMock);
    expect(event.module).toBe("error-boundary");
    expect(event.stack).toContain("at PainelAdmin");
  });

  it("deduplica a mesma mensagem na mesma tela", () => {
    const fetchMock = stubFetch();

    reportClientError(new Error("Falha repetida"));
    reportClientError(new Error("Falha repetida"));

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("respeita o teto de envios por sessão", () => {
    const fetchMock = stubFetch();

    for (let index = 0; index < 25; index += 1) {
      reportClientError(new Error(`Falha número ${index}`));
    }

    expect(fetchMock).toHaveBeenCalledTimes(20);
  });

  it("não lança quando o envio falha", async () => {
    stubFetch(() => Promise.reject(new TypeError("sem rede")));

    expect(() => reportClientError(new Error("Falha de rede"))).not.toThrow();
    await Promise.resolve();
    await Promise.resolve();
  });

  it("ignora ruído conhecido e erros de cancelamento", () => {
    const fetchMock = stubFetch();
    const abortError = new Error("A operação foi cancelada");
    abortError.name = "AbortError";

    handleGlobalError({
      error: new Error("ResizeObserver loop limit exceeded"),
    } as ErrorEvent);
    handleUnhandledRejection({ reason: abortError } as PromiseRejectionEvent);
    handleUnhandledRejection({ reason: new Error("Falha real") } as PromiseRejectionEvent);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(sentEvents(fetchMock)[0]?.message).toBe("Falha real");
  });
});
