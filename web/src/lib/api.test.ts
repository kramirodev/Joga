import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, api, clearAuthTokens, refreshSession, setAuthTokens } from "./api";

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
