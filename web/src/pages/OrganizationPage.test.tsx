import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthContext } from "../lib/auth-context";
import { ToastProvider } from "../components/ui/Toast";
import type { Booking, Member, Organization, Receivable, Role, Venue } from "../types";
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
    latitude: -22.9,
    longitude: -43.2,
    postal_code: "20541004",
    geocoding_source: "brasilapi",
    geocoding_precision: "street",
    geocoded_at: "2026-11-01T12:00:00Z",
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
  organization_venue_name: "Quadra Central",
  venue_space_name: "Quadra 1",
  format_id: "format-1",
  format_name: "Futebol 2x2",
  band_code: "economica_dia",
  band_label: "Econômica dia",
  tickets_per_seat: 6,
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
  presence_closed_at: null,
  players_per_team: null,
  formation_note: null,
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
  timezone: "America/Sao_Paulo",
};

const receivable: Receivable = {
  booking_id: "booking-1",
  release_id: "release-1",
  amount_cents: 40000,
  status: "PENDING",
  eligible_at: "2026-12-16T19:00:00Z",
  released_at: null,
  starts_at: "2026-12-15T18:00:00Z",
  ends_at: "2026-12-15T19:00:00Z",
  has_open_dispute: false,
  dispute_id: null,
  venue_price_cents: 40000,
  fee_cents: 8000,
  total_cents: 48000,
  receipt_reference: null,
  dispute_deadline: "2026-12-19T19:00:00Z",
  reason: null,
};

function organizationFor(
  role: Role,
  verification: Organization["verification_status"] = "verified",
): Organization {
  const verified = verification === "verified";
  return {
    id: "org-1",
    name: "Arena Tijuca",
    status: "active",
    role,
    cnpj: verified ? "11222333000181" : null,
    cnpj_status: verified ? "ATIVA" : null,
    verification_status: verification,
    cnpj_verified_at: verified ? "2026-11-01T12:00:00Z" : null,
    cnpj_next_check_at: verified ? "2026-11-08T12:00:00Z" : null,
    payout_ready: true,
    payout_status: "active",
    pix_key_type: "cnpj",
    pix_key_masked: "****0001",
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

function stubApi(
  role: Role,
  bookings: Booking[] = [],
  verification: Organization["verification_status"] = "verified",
) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const path = new URL(url, "http://joga.local").pathname;
    if (path === "/api/v1/organizations/org-1/verification" && init?.method === "POST") {
      return jsonResponse(organizationFor(role, "verified"));
    }
    if (path === "/api/v1/organizations/org-1") {
      return jsonResponse(organizationFor(role, verification));
    }
    if (url.includes("/bookings/booking-1/accept")) {
      return jsonResponse({ ...booking, status: "PAYMENT_PENDING" });
    }
    if (path.endsWith("/members")) return jsonResponse({ members });
    if (path === "/api/v1/organizations/org-1/venues/venue-1" && init?.method === "PATCH") {
      return jsonResponse({ ...venues[0], name: "Quadra Central Editada" });
    }
    if (path.endsWith("/venues")) return jsonResponse({ venues });
    if (path.endsWith("/bookings")) {
      return jsonResponse({
        bookings,
        total: bookings.length,
        limit: 50,
        offset: 0,
      });
    }
    if (path.endsWith("/financial/summary")) {
      return jsonResponse({
        charged_cents: 0,
        paid_cents: 0,
        refunded_cents: 0,
        pending_cents: 0,
        released_cents: 0,
        pending_release_cents: 40000,
        reversed_cents: 0,
        failed_cents: 0,
        disputed_cents: 0,
        venue_price_cents: 40000,
        joga_fee_cents: 8000,
        payments: 0,
        refunds: 0,
      });
    }
    if (path.endsWith("/financial/commission")) {
      return jsonResponse({
        rows: [],
        totals: {
          bookings: 0,
          venue_price_cents: 0,
          joga_fee_cents: 0,
          total_cents: 0,
        },
        limit: 50,
        offset: 0,
      });
    }
    if (path.endsWith("/financial/receivables")) {
      return jsonResponse({
        receivables: [receivable],
        total: 1,
        limit: 50,
        offset: 0,
      });
    }
    if (path.endsWith("/financial/statement")) {
      return jsonResponse({ entries: [], total: 0, limit: 50, offset: 0 });
    }
    if (path.endsWith("/financial/disputes")) {
      if (init?.method === "POST") {
        return jsonResponse(
          {
            id: "dispute-1",
            organization_id: "org-1",
            booking_id: "booking-1",
            release_id: "release-1",
            amount_cents: 40000,
            status: "OPEN",
            deadline_at: "2026-12-19T19:00:00Z",
            reason: "Valor divergente",
            evidence: null,
            decision_reason: null,
            decided_by: null,
            decided_at: null,
            created_by: "user-1",
            created_at: "2026-12-01T12:00:00Z",
            updated_at: "2026-12-01T12:00:00Z",
          },
          201,
        );
      }
      return jsonResponse({ disputes: [], total: 0, limit: 50, offset: 0 });
    }
    if (path.endsWith("/payout") && init?.method === "PUT") {
      return jsonResponse(organizationFor(role));
    }
    if (url.includes("/audit")) {
      return jsonResponse({ audit: [], total: 0, limit: 50, offset: 0 });
    }
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
      <ToastProvider>
        <MemoryRouter initialEntries={["/organizations/org-1"]}>
          <AuthContext.Provider
            value={{
              user: { id: "user-1", status: "active" },
              capabilities: [],
              loading: false,
              sessionExpired: false,
              signIn: vi.fn(),
              signOut: vi.fn(),
            }}
          >
            <Routes>
              <Route path="/organizations/:organizationId" element={<OrganizationPage />} />
            </Routes>
          </AuthContext.Provider>
        </MemoryRouter>
      </ToastProvider>
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
    expect(await screen.findByText("Ana")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: /Estabelecimentos/ }));
    expect(await screen.findByText("Quadra Central")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Novo estabelecimento" })).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/audit"))).toBe(false);

    await user.click(screen.getByRole("tab", { name: /Financeiro/ }));
    expect(await screen.findByText(/repasse elegível em/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Contestar repasse" })).not.toBeInTheDocument();
  });

  it("proprietário vê edição, gestão de membros e auditoria", async () => {
    const fetchMock = stubApi("OWNER");
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByRole("heading", { name: "Arena Tijuca" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Editar nome" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Adicionar membro" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Auditoria" })).toBeInTheDocument();
    expect(await screen.findByLabelText("Papel de Ana")).toHaveValue("OWNER");
    await user.click(screen.getByRole("tab", { name: "Auditoria" }));
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/audit"))).toBe(true),
    );
  });

  it("proprietário contesta um recebível pendente", async () => {
    const fetchMock = stubApi("OWNER");
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByRole("heading", { name: "Arena Tijuca" })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: /Financeiro/ }));
    await user.click(await screen.findByRole("button", { name: "Contestar repasse" }));
    await user.type(screen.getByLabelText("Motivo da contestação"), "Valor divergente");
    await user.click(screen.getByRole("button", { name: "Registrar contestação" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([url, init]) =>
            String(url).includes("/financial/disputes") &&
            (init as RequestInit | undefined)?.method === "POST",
        ),
      ).toBe(true),
    );
  });

  it("operador aceita uma reserva pendente", async () => {
    const fetchMock = stubApi("OPERATOR", [booking]);
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByRole("heading", { name: "Arena Tijuca" })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: /Reservas/ }));
    await user.click(await screen.findByRole("button", { name: "Aceitar solicitação" }));
    await user.click(
      screen.getByRole("checkbox", {
        name: /Confirmo que o horário já está bloqueado/,
      }),
    );
    await user.click(screen.getByRole("button", { name: "Confirmar bloqueio" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) => String(url).includes("/bookings/booking-1/accept")),
      ).toBe(true),
    );
  });

  it("proprietário configura o destino de repasse", async () => {
    const fetchMock = stubApi("OWNER");
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByRole("heading", { name: "Arena Tijuca" })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: /Financeiro/ }));
    await user.type(await screen.findByLabelText("CNPJ"), "11222333000181");
    await user.type(screen.getByLabelText("Chave Pix"), "11222333000181");
    await user.click(screen.getByRole("button", { name: /Salvar destino de repasse/ }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([url, init]) =>
            String(url).includes("/payout") && (init as RequestInit | undefined)?.method === "PUT",
        ),
      ).toBe(true),
    );
  });

  it("edita o estabelecimento pelo modal", async () => {
    const fetchMock = stubApi("OWNER");
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("tab", { name: /Estabelecimentos/ }));
    await user.click(await screen.findByRole("button", { name: "Editar" }));

    const dialog = await screen.findByRole("dialog");
    const name = within(dialog).getByLabelText("Nome");
    await user.clear(name);
    await user.type(name, "Quadra Central Editada");
    await user.click(within(dialog).getByRole("button", { name: "Salvar alterações" }));

    expect(await screen.findByText("Estabelecimento atualizado")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([url, init]) =>
            String(url).includes("/venues/venue-1") &&
            (init as RequestInit | undefined)?.method === "PATCH",
        ),
      ).toBe(true),
    );
  });

  it("mostra o CNPJ verificado e os dados da conferência", async () => {
    stubApi("OWNER");
    renderPage();

    expect(
      await screen.findByRole("heading", { name: "Cadastro empresarial" }),
    ).toBeInTheDocument();
    expect(screen.getByText("11.222.333/0001-81")).toBeInTheDocument();
    expect(screen.getByText("CNPJ verificado")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Verificar CNPJ" })).not.toBeInTheDocument();
  });

  it("organização pendente bloqueia quadras e permite regularizar o CNPJ", async () => {
    const fetchMock = stubApi("OWNER", [], "pending");
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText("Verificação pendente")).toBeInTheDocument();
    expect(
      screen.getByText(/Esta organização ainda não teve o CNPJ verificado/),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: /Estabelecimentos/ }));
    expect(
      await screen.findByText(/O CNPJ desta organização precisa estar verificado/),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Nome")).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Verificar CNPJ" }));
    const dialog = screen.getByRole("dialog", { name: "Verificar CNPJ" });
    expect(within(dialog).getByLabelText("CPF do responsável")).toHaveValue("");
    await user.type(within(dialog).getByLabelText("CNPJ"), "11222333000181");
    await user.type(within(dialog).getByLabelText("CPF do responsável"), "11144477735");
    await user.click(within(dialog).getByRole("button", { name: "Verificar CNPJ" }));

    expect(
      await screen.findByText(
        "A organização está regularizada e já pode cadastrar e publicar quadras.",
      ),
    ).toBeInTheDocument();
    await waitFor(() => {
      const call = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).includes("/organizations/org-1/verification") &&
          (init as RequestInit | undefined)?.method === "POST",
      );
      expect(call).toBeTruthy();
      expect(JSON.parse(String((call?.[1] as RequestInit).body))).toEqual({
        cnpj: "11222333000181",
        cpf: "11144477735",
      });
    });
  });
});
