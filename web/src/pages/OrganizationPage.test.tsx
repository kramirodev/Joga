import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthContext } from "../lib/auth-context";
import type { Member, Organization, Role, Venue } from "../types";
import { OrganizationPage } from "./OrganizationPage";

const members: Member[] = [
  {
    user_id: "user-1",
    display_name: "Ana",
    role: "OWNER",
    created_at: "2026-11-01T12:00:00Z",
  },
];

const venues: Venue[] = [
  {
    id: "venue-1",
    organization_id: "org-1",
    venue_id: null,
    name: "Quadra Central",
    city: "Rio de Janeiro",
    state: "RJ",
    address_line: null,
    timezone: "America/Sao_Paulo",
    status: "active",
    created_at: "2026-11-01T12:00:00Z",
    updated_at: "2026-11-01T12:00:00Z",
  },
];

function organizationFor(role: Role): Organization {
  return {
    id: "org-1",
    name: "Arena Tijuca",
    status: "active",
    role,
    created_at: "2026-11-01T12:00:00Z",
    updated_at: "2026-11-01T12:00:00Z",
  };
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubApi(role: Role) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith("/api/v1/organizations/org-1")) {
      return jsonResponse(organizationFor(role));
    }
    if (url.endsWith("/members")) return jsonResponse({ members });
    if (url.endsWith("/venues")) return jsonResponse({ venues });
    if (url.includes("/audit")) return jsonResponse({ audit: [], limit: 50, offset: 0 });
    return jsonResponse({ detail: { code: "not_found" } }, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/organizations/org-1"]}>
        <AuthContext.Provider
          value={{
            user: { id: "user-1", status: "active" },
            loading: false,
            signIn: vi.fn(),
            signOut: vi.fn(),
          }}
        >
          <Routes>
            <Route path="/organizations/:organizationId" element={<OrganizationPage />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("OrganizationPage — permissões na interface", () => {
  it("operador consulta membros e estabelecimentos, mas não administra", async () => {
    const fetchMock = stubApi("OPERATOR");
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByRole("heading", { name: "Arena Tijuca" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Editar nome" })).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Auditoria" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Adicionar membro" })).not.toBeInTheDocument();
    expect(screen.getByText("Ana")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: /Estabelecimentos/ }));
    expect(screen.getByText("Quadra Central")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Novo estabelecimento" })).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/audit"))).toBe(false);
  });

  it("proprietário vê edição, gestão de membros e auditoria", async () => {
    const fetchMock = stubApi("OWNER");
    renderPage();

    expect(await screen.findByRole("heading", { name: "Arena Tijuca" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Editar nome" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Adicionar membro" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Auditoria" })).toBeInTheDocument();
    expect(screen.getByLabelText("Papel de Ana")).toHaveValue("OWNER");
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/audit"))).toBe(true),
    );
  });
});
