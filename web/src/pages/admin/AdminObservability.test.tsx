import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  ObservabilityAlertsResponse,
  ObservabilityEvent,
  ObservabilityEventDetail,
  ObservabilityIpReport,
  ObservabilitySummaryResponse,
  ObservabilitySummaryWindow,
} from "../../types";
import { AdminObservabilityEventPage } from "./AdminObservabilityEventPage";
import { AdminObservabilityEventsPage } from "./AdminObservabilityEventsPage";
import { AdminObservabilityIpPage } from "./AdminObservabilityIpPage";
import { AdminObservabilityPage } from "./AdminObservabilityPage";
import { AdminObservabilityUserPage } from "./AdminObservabilityUserPage";

const OCCURRED_AT = "2026-11-26T10:00:00Z";

function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

const event: ObservabilityEvent = {
  id: "evt-1",
  occurred_at: OCCURRED_AT,
  level: "error",
  category: "http",
  source: "log_events",
  module: "bookings",
  request_id: "req-1",
  correlation_id: "corr-1",
  user_id: "user-1",
  ip: "203.0.113.***",
  ip_masked: true,
  user_agent: "Mozilla/5.0",
  endpoint: "/bookings",
  status: 500,
  duration_ms: 1200,
  message: "Tempo esgotado ao salvar reserva",
  error_code: "timeout",
  details: { booking_id: "b-1" },
};

const secondEvent: ObservabilityEvent = {
  ...event,
  id: "evt-2",
  message: "Falha ao confirmar pagamento",
  level: "warn",
  status: 409,
};

const eventDetail: ObservabilityEventDetail = {
  ...event,
  ip: "203.0.113.9",
  ip_masked: false,
  stack: "Error: tempo esgotado\n    at saveBooking (/app/bookings.py:42)",
  result: "failure",
  details: { booking_id: "b-1", attempt: 2 },
};

function summaryWindow(
  overrides: Partial<ObservabilitySummaryWindow> = {},
): ObservabilitySummaryWindow {
  return {
    from_at: "2026-11-25T10:00:00Z",
    to_at: OCCURRED_AT,
    total_events: 111,
    by_level: [
      { level: "debug", count: 1 },
      { level: "info", count: 100 },
      { level: "warn", count: 5 },
      { level: "error", count: 3 },
      { level: "fatal", count: 1 },
    ],
    by_category: [{ category: "http", count: 80 }],
    http: { requests: 120, status_4xx: 8, status_5xx: 2, slow_requests: 4, avg_duration_ms: 850 },
    auth: { unauthorized: 2, forbidden: 1, rate_limited: 3, failed_logins: 6 },
    jobs: { started: 4, finished: 3, failed: 1 },
    audit_events: 4,
    security_events: 9,
    suspicious_users: [
      {
        user_id: "user-9",
        events: 12,
        security_events: 4,
        last_seen_at: OCCURRED_AT,
      },
    ],
    ...overrides,
  };
}

const summary: ObservabilitySummaryResponse = {
  window: "24h",
  current: summaryWindow(),
  previous: summaryWindow({
    by_level: [
      { level: "info", count: 90 },
      { level: "warn", count: 4 },
      { level: "error", count: 2 },
    ],
    http: { requests: 100, status_4xx: 5, status_5xx: 1, slow_requests: 6, avg_duration_ms: 900 },
    auth: { unauthorized: 1, forbidden: 1, rate_limited: 1, failed_logins: 3 },
    jobs: { started: 3, finished: 3, failed: 0 },
    suspicious_users: [],
  }),
};

const alerts: ObservabilityAlertsResponse = {
  window: "24h",
  from_at: "2026-11-25T10:00:00Z",
  to_at: OCCURRED_AT,
  alerts: [
    { code: "login_failures", level: "warning", count: 12, threshold: 10 },
    { code: "server_errors", level: "critical", count: 4, threshold: 1 },
  ],
};

type FetchMock = ReturnType<typeof vi.fn>;

interface Call {
  path: string;
  method: string;
  search: URLSearchParams;
}

function calls(fetchMock: FetchMock): Call[] {
  return fetchMock.mock.calls.map((raw) => {
    const [input, init] = raw as [RequestInfo | URL, RequestInit | undefined];
    const url = new URL(String(input), "http://joga.local");
    return {
      path: url.pathname,
      method: (init?.method ?? "GET").toUpperCase(),
      search: url.searchParams,
    };
  });
}

type Handler = (url: URL, init?: RequestInit) => Response | Promise<Response>;

function stubFetch(handler: Handler): FetchMock {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) =>
    handler(new URL(String(input), "http://joga.local"), init),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderPage(path: string, element: ReactElement, pattern = "*") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={pattern} element={element} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Monitoramento", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: vi.fn(() => "blob:mock"),
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: vi.fn(),
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("mostra o resumo com comparação e atalhos", async () => {
    const fetchMock = stubFetch((url) => {
      if (url.pathname === "/api/v1/admin/observability/summary") {
        return jsonResponse({ ...summary, window: url.searchParams.get("window") ?? "24h" });
      }
      return jsonResponse({ detail: { code: "not_found" } }, 404);
    });
    const user = userEvent.setup();
    renderPage("/admin/observability", <AdminObservabilityPage />, "/admin/observability");

    expect(await screen.findByRole("heading", { name: "Monitoramento" })).toBeInTheDocument();

    const errorsCard = (await screen.findByText("Erros")).closest(".stat-card");
    expect(errorsCard).not.toBeNull();
    expect(within(errorsCard as HTMLElement).getByText("3")).toBeInTheDocument();

    const warningsCard = screen.getByText("Avisos").closest(".stat-card");
    expect(within(warningsCard as HTMLElement).getByText("5")).toBeInTheDocument();
    expect(screen.getByText("+25% em relação ao período anterior")).toBeInTheDocument();
    expect(screen.getByText("120")).toBeInTheDocument();
    expect(screen.getByText("850 ms")).toBeInTheDocument();
    expect(screen.getByText("6,7% das requisições")).toBeInTheDocument();
    expect(screen.getByText("1,7% das requisições")).toBeInTheDocument();

    const suspicious = screen.getByRole("link", { name: /user-9/ });
    expect(suspicious).toHaveAttribute("href", "/admin/observability/users/user-9");

    await user.click(screen.getByRole("button", { name: "Últimos 7 dias" }));
    await waitFor(() =>
      expect(
        calls(fetchMock).some(
          (call) =>
            call.path === "/api/v1/admin/observability/summary" &&
            call.search.get("window") === "7d",
        ),
      ).toBe(true),
    );
  });

  it("mostra os alertas ativos com links para o explorador filtrado", async () => {
    stubFetch((url) => {
      if (url.pathname === "/api/v1/admin/observability/alerts") {
        return jsonResponse({ ...alerts, window: url.searchParams.get("window") ?? "24h" });
      }
      if (url.pathname === "/api/v1/admin/observability/summary") {
        return jsonResponse({ ...summary, window: url.searchParams.get("window") ?? "24h" });
      }
      return jsonResponse({ detail: { code: "not_found" } }, 404);
    });
    renderPage("/admin/observability", <AdminObservabilityPage />, "/admin/observability");

    expect(await screen.findByRole("link", { name: /Falhas de acesso/ })).toBeInTheDocument();
    expect(screen.getByText("12 ocorrências · limite de 10")).toBeInTheDocument();
    expect(screen.getByText("4 ocorrências · limite de 1")).toBeInTheDocument();
    expect(screen.getByText("Crítico")).toBeInTheDocument();

    expect(screen.getByRole("link", { name: /Falhas de acesso/ })).toHaveAttribute(
      "href",
      "/admin/observability/events?category=security",
    );
    expect(screen.getByRole("link", { name: /Erros do servidor/ })).toHaveAttribute(
      "href",
      "/admin/observability/events?level=error&category=http",
    );
  });

  it("mostra vazio quando não há alertas ativos", async () => {
    stubFetch((url) => {
      if (url.pathname === "/api/v1/admin/observability/alerts") {
        return jsonResponse({ ...alerts, alerts: [] });
      }
      if (url.pathname === "/api/v1/admin/observability/summary") {
        return jsonResponse(summary);
      }
      return jsonResponse({ detail: { code: "not_found" } }, 404);
    });
    renderPage("/admin/observability", <AdminObservabilityPage />, "/admin/observability");

    expect(await screen.findByText("Nenhum alerta ativo no período.")).toBeInTheDocument();
  });

  it("mostra o erro do endpoint de alertas com nova tentativa", async () => {
    stubFetch((url) => {
      if (url.pathname === "/api/v1/admin/observability/alerts") {
        return jsonResponse({ detail: { code: "request_failed" } }, 500);
      }
      if (url.pathname === "/api/v1/admin/observability/summary") {
        return jsonResponse(summary);
      }
      return jsonResponse({ detail: { code: "not_found" } }, 404);
    });
    renderPage("/admin/observability", <AdminObservabilityPage />, "/admin/observability");

    expect(
      await screen.findByText(/O servidor encontrou um erro ao processar a operação/),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Tentar novamente/ })).toBeInTheDocument();
  });

  it("mostra ausência de taxa quando não há requisições", async () => {
    const zeroTraffic = {
      requests: 0,
      status_4xx: 0,
      status_5xx: 0,
      slow_requests: 0,
      avg_duration_ms: null,
    };
    stubFetch(() =>
      jsonResponse({
        window: "24h",
        current: summaryWindow({ http: zeroTraffic }),
        previous: summaryWindow({ http: zeroTraffic }),
      }),
    );
    renderPage("/admin/observability", <AdminObservabilityPage />, "/admin/observability");

    expect((await screen.findAllByText("sem requisições no período")).length).toBe(2);
  });

  it("aplica filtros, pagina por cursor e mostra vazio no explorador", async () => {
    const fetchMock = stubFetch((url) => {
      if (url.pathname === "/api/v1/admin/observability/events") {
        if (url.searchParams.get("cursor") === "cursor-1") {
          return jsonResponse({ events: [secondEvent], next_cursor: null });
        }
        return jsonResponse({ events: [event], next_cursor: "cursor-1" });
      }
      return jsonResponse({ detail: { code: "not_found" } }, 404);
    });
    const user = userEvent.setup();
    renderPage(
      "/admin/observability/events",
      <AdminObservabilityEventsPage />,
      "/admin/observability/events",
    );

    expect(await screen.findByText("Tempo esgotado ao salvar reserva")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Nível"), "error");
    await user.type(screen.getByLabelText("Busca"), "timeout");
    await user.click(screen.getByRole("button", { name: "Buscar" }));

    await waitFor(() =>
      expect(
        calls(fetchMock).some(
          (call) =>
            call.path === "/api/v1/admin/observability/events" &&
            call.search.get("level") === "error" &&
            call.search.get("q") === "timeout",
        ),
      ).toBe(true),
    );

    await user.click(screen.getByRole("button", { name: "Carregar mais" }));
    expect(await screen.findByText("Falha ao confirmar pagamento")).toBeInTheDocument();
    expect(
      calls(fetchMock).some(
        (call) =>
          call.path === "/api/v1/admin/observability/events" &&
          call.search.get("cursor") === "cursor-1",
      ),
    ).toBe(true);
  });

  it("mostra estado vazio quando não há eventos", async () => {
    stubFetch(() => jsonResponse({ events: [], next_cursor: null }));
    renderPage(
      "/admin/observability/events",
      <AdminObservabilityEventsPage />,
      "/admin/observability/events",
    );

    expect(await screen.findByText("Nenhum evento encontrado")).toBeInTheDocument();
  });

  it("mostra mensagem própria para 403", async () => {
    stubFetch(() => jsonResponse({ detail: { code: "platform_admin_required" } }, 403));
    renderPage("/admin/observability", <AdminObservabilityPage />, "/admin/observability");

    expect((await screen.findAllByText("Acesso restrito")).length).toBeGreaterThan(0);
  });

  it("mostra aviso de limite de tentativas com nova tentativa", async () => {
    stubFetch(() =>
      jsonResponse({ detail: { code: "rate_limited" } }, 429, { "Retry-After": "30" }),
    );
    renderPage("/admin/observability", <AdminObservabilityPage />, "/admin/observability");

    expect((await screen.findAllByText(/Muitas tentativas/)).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: /Tentar novamente/ }).length).toBeGreaterThan(0);
  });

  it("mostra detalhe com rastreamento, metadados e identificadores copiáveis", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    stubFetch((url) => {
      if (url.pathname === "/api/v1/admin/observability/events/evt-1") {
        return jsonResponse(eventDetail);
      }
      return jsonResponse({ detail: { code: "not_found" } }, 404);
    });
    renderPage(
      "/admin/observability/events/evt-1",
      <AdminObservabilityEventPage />,
      "/admin/observability/events/:eventId",
    );

    expect(await screen.findByText(/at saveBooking/)).toBeInTheDocument();
    expect(screen.getByText(/booking_id/)).toBeInTheDocument();
    expect(screen.getByText("failure")).toBeInTheDocument();

    const requestLink = screen.getByRole("link", { name: "Eventos da mesma requisição" });
    expect(requestLink).toHaveAttribute("href", "/admin/observability/events?request_id=req-1");
    expect(screen.getByRole("link", { name: "Eventos deste IP" })).toHaveAttribute(
      "href",
      "/admin/observability/ips/203.0.113.9",
    );

    const copyButton = screen.getByRole("button", {
      name: "Copiar identificador da requisição",
    });
    await user.click(copyButton);
    await waitFor(() => expect(writeText).toHaveBeenCalledWith("req-1"));
    expect(copyButton).toHaveTextContent("Copiado");
  });

  it("carrega a cronologia do usuário e aplica filtros de categoria", async () => {
    const fetchMock = stubFetch((url) => {
      if (url.pathname === "/api/v1/admin/observability/users/user-1/activity") {
        return jsonResponse({ user_id: "user-1", events: [event], next_cursor: null });
      }
      return jsonResponse({ detail: { code: "not_found" } }, 404);
    });
    const user = userEvent.setup();
    renderPage(
      "/admin/observability/users/user-1",
      <AdminObservabilityUserPage />,
      "/admin/observability/users/:userId",
    );

    expect(await screen.findByText("Tempo esgotado ao salvar reserva")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Categoria"), "security");
    await user.click(screen.getByRole("button", { name: "Buscar" }));

    await waitFor(() =>
      expect(
        calls(fetchMock).some(
          (call) =>
            call.path === "/api/v1/admin/observability/users/user-1/activity" &&
            call.search.get("category") === "security",
        ),
      ).toBe(true),
    );
  });

  it("carrega o relatório de um endereço IP com contas e eventos", async () => {
    const report: ObservabilityIpReport = {
      ip: "203.0.113.9",
      ip_hash: "hash-1",
      first_seen_at: "2026-11-20T08:00:00Z",
      last_seen_at: OCCURRED_AT,
      total_events: 18,
      security_events: 3,
      failed_logins: 2,
      users: [{ user_id: "user-1", events: 5, last_seen_at: OCCURRED_AT }],
      events: [event],
    };
    stubFetch((url) => {
      if (url.pathname === "/api/v1/admin/observability/ips/203.0.113.9") {
        return jsonResponse(report);
      }
      return jsonResponse({ detail: { code: "not_found" } }, 404);
    });
    renderPage(
      "/admin/observability/ips/203.0.113.9",
      <AdminObservabilityIpPage />,
      "/admin/observability/ips/:ip",
    );

    expect(await screen.findByText("Tempo esgotado ao salvar reserva")).toBeInTheDocument();
    expect(screen.getByText("Eventos de segurança")).toBeInTheDocument();
    const userLinks = screen.getAllByRole("link", { name: /user-1/ });
    expect(
      userLinks.some((link) => link.getAttribute("href") === "/admin/observability/users/user-1"),
    ).toBe(true);
  });

  it("exporta CSV e JSON com os filtros e informa truncamento", async () => {
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);
    const fetchMock = stubFetch((url) => {
      if (url.pathname === "/api/v1/admin/observability/events") {
        return jsonResponse({ events: [event], next_cursor: null });
      }
      if (url.pathname === "/api/v1/admin/observability/export") {
        const format = url.searchParams.get("format") ?? "csv";
        return new Response(new Blob(["id\n1"], { type: "text/csv" }), {
          status: 200,
          headers: {
            "Content-Type": "text/csv",
            "X-Export-Rows": "2",
            "X-Export-Truncated": "true",
            "Content-Disposition": `attachment; filename="observabilidade.${format}"`,
          },
        });
      }
      return jsonResponse({ detail: { code: "not_found" } }, 404);
    });
    const user = userEvent.setup();
    renderPage(
      "/admin/observability/events",
      <AdminObservabilityEventsPage />,
      "/admin/observability/events",
    );

    await screen.findByText("Tempo esgotado ao salvar reserva");

    await user.click(screen.getByRole("button", { name: "Exportar CSV" }));
    expect(await screen.findByText(/Arquivo gerado com 2 eventos/)).toBeInTheDocument();
    expect(screen.getByText(/limite de exportação foi atingido/)).toBeInTheDocument();

    const csvCall = calls(fetchMock).find(
      (call) => call.path === "/api/v1/admin/observability/export",
    );
    expect(csvCall?.search.get("format")).toBe("csv");
    expect(csvCall?.search.get("full_ip")).toBe("false");
    expect(clickSpy).toHaveBeenCalled();

    await user.click(screen.getByLabelText("Incluir endereço IP completo"));
    await user.click(screen.getByRole("button", { name: "Exportar JSON" }));

    await waitFor(() =>
      expect(
        calls(fetchMock).some(
          (call) =>
            call.path === "/api/v1/admin/observability/export" &&
            call.search.get("format") === "json" &&
            call.search.get("full_ip") === "true",
        ),
      ).toBe(true),
    );
  });
});
