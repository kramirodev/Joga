import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "../../components/ui/Toast";
import type { Booking, Organization } from "../../types";
import { BookingsPanel } from "./BookingsPanel";

const organization: Organization = {
  id: "org-1",
  name: "Arena Tijuca",
  status: "active",
  role: "OWNER",
  cnpj: "11222333000181",
  cnpj_status: "ATIVA",
  verification_status: "verified",
  cnpj_verified_at: "2026-11-01T12:00:00Z",
  cnpj_next_check_at: "2026-11-08T12:00:00Z",
  payout_ready: true,
  payout_status: "active",
  pix_key_type: "cnpj",
  pix_key_masked: "****0001",
  created_at: "2026-11-01T12:00:00Z",
  updated_at: "2026-11-01T12:00:00Z",
};

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
  status: "CONFIRMED",
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
  confirmed_at: "2026-12-01T12:05:00Z",
  cancelled_at: null,
  expired_at: null,
  completed_at: null,
  presence_closed_at: null,
  players_per_team: 2,
  formation_note: null,
  cancellation_reason: null,
  created_at: "2026-12-01T12:00:00Z",
  updated_at: "2026-12-01T12:00:00Z",
  participants: [],
  timers: [],
  hold: null,
  payments: [
    {
      id: "payment-1",
      participant_id: "participant-1",
      version: 1,
      amount_cents: 4000,
      status: "PAID",
      paid_at: "2026-12-01T12:10:00Z",
    },
  ],
  timezone: "America/Sao_Paulo",
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubRefund(status: "PROCESSED" | "FAILED" | "PENDING") {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.includes("/refund") && init?.method === "POST") {
      return jsonResponse({ refunded: 1 });
    }
    if (url.endsWith("/financial")) {
      return jsonResponse({
        booking_id: "booking-1",
        ledger: [],
        refunds: [
          {
            id: "refund-1",
            booking_payment_id: "payment-1",
            amount_cents: 4000,
            status,
            reason: "Teste",
            provider_reference: "mp-1",
            processed_at: status === "PROCESSED" ? "2026-12-01T12:20:00Z" : null,
            created_at: "2026-12-01T12:20:00Z",
          },
        ],
      });
    }
    return jsonResponse({ detail: { code: "not_found" } }, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderPanel() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <BookingsPanel
          organization={organization}
          bookings={[booking]}
          total={1}
          limit={50}
          offset={0}
          filters={{ limit: 50, offset: 0 }}
          onParamsChange={vi.fn()}
          loading={false}
          fetching={false}
          error={null}
          onRetry={vi.fn()}
        />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

async function requestRefund() {
  const user = userEvent.setup();
  renderPanel();
  await user.click(await screen.findByRole("button", { name: "Reembolsar" }));
  const dialog = await screen.findByRole("dialog");
  await user.type(within(dialog).getByLabelText("Motivo do reembolso"), "Cancelamento");
  await user.click(within(dialog).getByRole("button", { name: "Reembolsar" }));
}

describe("BookingsPanel — reembolso", () => {
  it("mostra reembolso processado quando o provedor confirma", async () => {
    stubRefund("PROCESSED");
    await requestRefund();

    expect(await screen.findByText("Reembolso processado")).toBeInTheDocument();
    expect(screen.getByText(/estornada\(s\) pelo Mercado Pago/)).toBeInTheDocument();
  });

  it("não mostra sucesso quando o provedor recusa", async () => {
    stubRefund("FAILED");
    await requestRefund();

    expect(await screen.findByText("Reembolso não concluído")).toBeInTheDocument();
    expect(screen.queryByText("Reembolso processado")).not.toBeInTheDocument();
    expect(screen.getByText(/não foram estornadas/)).toBeInTheDocument();
  });
});
