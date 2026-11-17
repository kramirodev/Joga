import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  SESSION_EXPIRED_EVENT,
  api,
  clearAuthTokens,
  refreshSession,
  requestPhoneChallenge,
  setAuthTokens,
} from "./api";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("cliente HTTP do painel", () => {
  beforeEach(() => {
    clearAuthTokens();
  });

  it("envia Authorization e CSRF em operações de escrita", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        id: "org-1",
        name: "Arena Tijuca",
        status: "active",
        role: "OWNER",
        created_at: "2026-11-07T12:00:00Z",
        updated_at: "2026-11-07T12:00:00Z",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    setAuthTokens({ accessToken: "access-1", csrfToken: "csrf-1" });

    await api.createOrganization("Arena Tijuca");

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Headers;
    expect(url).toBe("/api/v1/organizations");
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("same-origin");
    expect(headers.get("Authorization")).toBe("Bearer access-1");
    expect(headers.get("X-CSRF-Token")).toBe("csrf-1");
    expect(headers.get("Content-Type")).toBe("application/json");
  });

  it("não envia CSRF em leitura autenticada", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ organizations: [] }));
    vi.stubGlobal("fetch", fetchMock);
    setAuthTokens({ accessToken: "access-1", csrfToken: "csrf-1" });

    await api.listOrganizations();

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer access-1");
    expect(headers.get("X-CSRF-Token")).toBeNull();
  });

  it("renova a sessão em 401 e repete a requisição", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: { code: "invalid_token" } }, 401))
      .mockResolvedValueOnce(
        jsonResponse({
          access_token: "access-2",
          access_expires_at: "2026-11-07T13:00:00Z",
          csrf_token: "csrf-2",
          user: { id: "user-1", status: "active" },
          capabilities: [],
        }),
      )
      .mockResolvedValueOnce(jsonResponse({ organizations: [] }));
    vi.stubGlobal("fetch", fetchMock);
    setAuthTokens({ accessToken: "access-1", csrfToken: "csrf-1" });

    const result = await api.listOrganizations();

    expect(result.organizations).toEqual([]);
    expect(fetchMock).toHaveBeenCalledTimes(3);

    const [refreshUrl, refreshInit] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(refreshUrl).toBe("/api/v1/auth/web/refresh");
    expect(refreshInit.method).toBe("POST");
    expect((refreshInit.headers as Record<string, string>)["X-CSRF-Token"]).toBe("csrf-1");

    const [, retryInit] = fetchMock.mock.calls[2] as [string, RequestInit];
    expect((retryInit.headers as Headers).get("Authorization")).toBe("Bearer access-2");
  });

  it("não tenta renovar sem CSRF", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await expect(refreshSession()).resolves.toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("converte erro do backend em ApiError com código", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementation(async () => jsonResponse({ detail: { code: "forbidden" } }, 403));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.getOrganization("org-1")).rejects.toBeInstanceOf(ApiError);
    await expect(api.getOrganization("org-1")).rejects.toMatchObject({
      name: "ApiError",
      status: 403,
      code: "forbidden",
    });
  });

  it("envia filtros e paginação de reservas com from/to codificados", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        bookings: [],
        total: 120,
        limit: 25,
        offset: 50,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await api.listOrganizationBookings("org-1", {
      status: "REQUESTED",
      from: "2026-11-15T00:00:00+03:00",
      to: "2026-11-30T23:59:59+03:00",
      limit: 25,
      offset: 50,
    });

    const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
    const parsed = new URL(url, "http://joga.local");
    expect(parsed.pathname).toBe("/api/v1/organizations/org-1/bookings");
    expect(parsed.searchParams.get("status")).toBe("REQUESTED");
    expect(parsed.searchParams.get("from")).toBe("2026-11-15T00:00:00+03:00");
    expect(parsed.searchParams.get("to")).toBe("2026-11-30T23:59:59+03:00");
    expect(parsed.searchParams.get("limit")).toBe("25");
    expect(parsed.searchParams.get("offset")).toBe("50");
    expect(url).toContain("from=2026-11-15T00%3A00%3A00%2B03%3A00");
    expect(result.total).toBe(120);
  });

  it("envia limit=50 e offset=0 por padrão nas reservas", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ bookings: [], total: 0, limit: 50, offset: 0 }));
    vi.stubGlobal("fetch", fetchMock);

    await api.listOrganizationBookings("org-1");

    const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
    const parsed = new URL(url, "http://joga.local");
    expect(parsed.searchParams.get("limit")).toBe("50");
    expect(parsed.searchParams.get("offset")).toBe("0");
    expect(parsed.searchParams.has("status")).toBe(false);
    expect(parsed.searchParams.has("from")).toBe(false);
    expect(parsed.searchParams.has("to")).toBe(false);
  });

  it("lê code, message e fields[] de erro 422", async () => {
    const fetchMock = vi.fn().mockImplementation(async () =>
      jsonResponse(
        {
          detail: {
            code: "validation_error",
            message: "Dados inválidos",
            fields: [
              {
                field: "query.limit",
                code: "less_than_equal",
                message: "Input should be less than or equal to 100",
              },
            ],
          },
        },
        422,
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.listOrganizationBookings("org-1", { limit: 1000 })).rejects.toMatchObject({
      status: 422,
      code: "validation_error",
      message: "Dados inválidos",
      fields: [
        {
          field: "query.limit",
          code: "less_than_equal",
          message: "Input should be less than or equal to 100",
        },
      ],
    });
  });

  it("captura o Retry-After de respostas 429", async () => {
    const fetchMock = vi.fn().mockImplementation(
      async () =>
        new Response(JSON.stringify({ detail: { code: "rate_limited" } }), {
          status: 429,
          headers: {
            "Content-Type": "application/json",
            "Retry-After": "45",
          },
        }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(requestPhoneChallenge("+5511900000001", "login")).rejects.toMatchObject({
      status: 429,
      code: "rate_limited",
      retryAfterSeconds: 45,
    });
  });

  it("consome a central de moderação com filtro e paginação", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse({ notifications: [], unread_count: 3, limit: 30, offset: 30 }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const result = await api.listModerationNotifications({
      unreadOnly: true,
      limit: 30,
      offset: 30,
    });

    const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
    const parsed = new URL(url, "http://joga.local");
    expect(parsed.pathname).toBe("/api/v1/moderation/notifications");
    expect(parsed.searchParams.get("unread_only")).toBe("true");
    expect(parsed.searchParams.get("limit")).toBe("30");
    expect(parsed.searchParams.get("offset")).toBe("30");
    expect(result.unread_count).toBe(3);
  });

  it("marca todas as notificações internas como lidas", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ marked: 4, unread_count: 0 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await api.markAllModerationNotificationsRead();

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/v1/moderation/notifications/read-all");
    expect(init.method).toBe("POST");
    expect(result.marked).toBe(4);
  });

  it("envia a proveniência do CEP ao cadastrar estabelecimento", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        id: "venue-1",
        organization_id: "org-1",
        venue_id: null,
        name: "Arena Paulista",
        city: "São Paulo",
        state: "SP",
        address_line: "Avenida Paulista, 1578",
        latitude: -23.5475,
        longitude: -46.63611,
        postal_code: "01310100",
        geocoding_source: "brasilapi",
        geocoding_precision: "street",
        geocoded_at: "2026-11-15T12:00:00Z",
        timezone: "America/Sao_Paulo",
        status: "active",
        created_at: "2026-11-15T12:00:00Z",
        updated_at: "2026-11-15T12:00:00Z",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await api.createVenue("org-1", {
      name: "Arena Paulista",
      city: "São Paulo",
      state: "SP",
      address_line: "Avenida Paulista, 1578",
      latitude: -23.5475,
      longitude: -46.63611,
      postal_code: "01310-100",
      geocoding_source: "brasilapi",
      geocoding_precision: "street",
      timezone: "America/Sao_Paulo",
    });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(String(init.body)) as Record<string, unknown>;
    expect(body.postal_code).toBe("01310-100");
    expect(body.geocoding_source).toBe("brasilapi");
    expect(body.geocoding_precision).toBe("street");
    expect(body.latitude).toBe(-23.5475);
  });

  it("consulta CEP normalizando dígitos e número", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        postal_code: "20541004",
        street: "Rua Barão de Mesquita",
        neighborhood: "Tijuca",
        city: "Rio de Janeiro",
        state: "RJ",
        country: "BR",
        latitude: -22.9234,
        longitude: -43.2456,
        precision: "street",
        source: "brasilapi",
        resolved_at: "2026-11-15T12:00:00Z",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await api.lookupPostalCode("20.541-004", "1200");

    const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
    const parsed = new URL(url, "http://joga.local");
    expect(parsed.pathname).toBe("/api/v1/geo/postal-codes/20541004");
    expect(parsed.searchParams.get("number")).toBe("1200");
    expect(result.precision).toBe("street");
  });

  it("consulta CEP sem número", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        postal_code: "20541004",
        street: null,
        neighborhood: null,
        city: "Rio de Janeiro",
        state: "RJ",
        country: "BR",
        latitude: null,
        longitude: null,
        precision: "unresolved",
        source: "brasilapi",
        resolved_at: "2026-11-15T12:00:00Z",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await api.lookupPostalCode("20541004");

    const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
    const parsed = new URL(url, "http://joga.local");
    expect(parsed.pathname).toBe("/api/v1/geo/postal-codes/20541004");
    expect(parsed.search).toBe("");
  });

  it("dispara sessão expirada quando o refresh falha com 401", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/auth/web/refresh")) {
        return jsonResponse({ detail: { code: "invalid_refresh_token" } }, 401);
      }
      return jsonResponse({ detail: { code: "invalid_token" } }, 401);
    });
    vi.stubGlobal("fetch", fetchMock);
    setAuthTokens({ accessToken: "expired", csrfToken: "csrf-1" });

    const listener = vi.fn();
    window.addEventListener(SESSION_EXPIRED_EVENT, listener);

    await expect(api.getOrganization("org-1")).rejects.toMatchObject({ status: 401 });
    expect(listener).toHaveBeenCalledTimes(1);

    window.removeEventListener(SESSION_EXPIRED_EVENT, listener);
  });

  it("captura o X-Request-ID para referência de suporte", async () => {
    const fetchMock = vi.fn().mockImplementation(
      async () =>
        new Response(JSON.stringify({ detail: { code: "forbidden" } }), {
          status: 403,
          headers: {
            "Content-Type": "application/json",
            "X-Request-ID": "req-abc-123",
          },
        }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.getOrganization("org-1")).rejects.toMatchObject({
      requestId: "req-abc-123",
    });
  });
});
