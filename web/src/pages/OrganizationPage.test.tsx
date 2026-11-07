import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthContext } from "../lib/auth-context";
import type { Booking, Member, Organization, Role, Venue } from "../types";
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

const booking: Booking = {
  id: "booking-1",
  lobby_id: "lobby-1",
  organization_id: "org-1",
  organization_venue_id: "venue-1",
  venue_space_id: "space-1",
  status: "REQUESTED",
  starts_at: "2026-12-15T18:00:00Z",
  ends_at: "2026-12-15T19:00:00Z",
  price_cents: 40000,
  currency: "BRL",
  seats: 4,
  policy_version: "v1",
  cancellation_policy: "full_refund_until_confirmed",
  response_due_at: "2026-12-15T17:30:00Z",
  payment_due_at: null,
  hold_expires_at: null,
  accepted_at: null,
  confirmed_at: null,
  cancelled_at: null,
  expired_at: null,
  completed_at: null,
  cancellation_reason: null,
  created_at: "2026-12-01T12:00:00Z",
  updated_at: "2026-12-01T12:00:00Z",
  participants: [],
  timers: [
    {
      timer_type: "T2",
      status: "RUNNING",
      started_at: "2026-12-01T12:00:00Z",
      deadline_at: "2026-12-01T12:30:00Z",
      ended_at: null,
    },
  ],
  hold: null,
  payments: [],
};

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

function stubApi(role: Role, bookings: Booking[] = []) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith("/api/v1/organizations/org-1")) {
      return jsonResponse(organizationFor(role));
    }
    if (url.includes("/bookings/booking-1/accept")) {
      return jsonResponse({ ...booking, status: "PAYMENT_PENDING" });
    }
    if (url.endsWith("/members")) return jsonResponse({ members });
    if (url.endsWith("/venues")) return jsonResponse({ venues });
    if (url.endsWith("/bookings")) return jsonResponse({ bookings });
    if (url.endsWith("/financial/summary")) {
      return jsonResponse({
        charged_cents: 0,
        paid_cents: 0,
        refunded_cents: 0,
        pending_cents: 0,
        released_cents: 0,
        payments: 0,
        refunds: 0,
      });
    }
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
    expect(screen.getByRole("tab", { name: /Reservas/ })).toBeInTheDocument();
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

  it("operador aceita uma reserva pendente", async () => {
    const fetchMock = stubApi("OPERATOR", [booking]);
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByRole("heading", { name: "Arena Tijuca" })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: /Reservas/ }));
    await user.click(await screen.findByRole("button", { name: "Aceitar" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) => String(url).includes("/bookings/booking-1/accept")),
      ).toBe(true),
    );
  });
});
