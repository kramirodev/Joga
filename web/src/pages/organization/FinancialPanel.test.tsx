import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "../../components/ui/Toast";
import { formatMoney } from "../../lib/format";
import type {
  BookingFinancialResponse,
  CommissionResponse,
  FinancialDispute,
  FinancialStatementEntry,
  Organization,
  OrganizationFinancialSummary,
  Receivable,
} from "../../types";
import { FinancialPanel } from "./FinancialPanel";

const money = (cents: number) =>
  new RegExp(
    formatMoney(cents)
      .replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
      .replace(/\s/g, "\\s*"),
  );

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

const summary: OrganizationFinancialSummary = {
  charged_cents: 48000,
  paid_cents: 48000,
  refunded_cents: 0,
  pending_cents: 0,
  released_cents: 0,
  pending_release_cents: 40000,
  reversed_cents: 0,
  failed_cents: 500,
  disputed_cents: 0,
  venue_price_cents: 40000,
  joga_fee_cents: 8000,
  payments: 1,
  refunds: 0,
};

const pendingReceivable: Receivable = {
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
  dispute_deadline: "2099-12-19T19:00:00Z",
  reason: null,
};

const releasedReceivable: Receivable = {
  ...pendingReceivable,
  booking_id: "booking-2",
  release_id: "release-2",
  status: "RELEASED",
  released_at: "2026-12-16T19:05:00Z",
  receipt_reference: "simulated:release-2",
  starts_at: "2026-12-17T18:00:00Z",
  ends_at: "2026-12-17T19:00:00Z",
};

const statementEntry: FinancialStatementEntry = {
  id: "ledger-1",
  booking_id: "booking-1",
  booking_payment_id: null,
  release_id: null,
  entry_type: "PAYMENT_CONFIRMED",
  direction: "CREDIT",
  amount_cents: 40000,
  venue_price_cents: 40000,
  fee_cents: 8000,
  total_cents: 48000,
  status: "POSTED",
  details: { kind: "booking", idempotency_key: "k1" },
  created_at: "2026-12-01T12:00:00Z",
};

const releaseEntry: FinancialStatementEntry = {
  ...statementEntry,
  id: "ledger-2",
  release_id: "release-1",
  entry_type: "VENUE_RELEASE",
  direction: "DEBIT",
  amount_cents: 40000,
  created_at: "2026-12-16T19:00:00Z",
};

const commission: CommissionResponse = {
  rows: [
    {
      booking_id: "booking-1",
      starts_at: "2026-12-15T18:00:00Z",
      confirmed_at: "2026-12-01T12:00:00Z",
      venue_price_cents: 40000,
      fee_cents: 8000,
      total_cents: 48000,
      release_status: "PENDING",
    },
  ],
  totals: {
    bookings: 1,
    venue_price_cents: 40000,
    joga_fee_cents: 8000,
    total_cents: 48000,
  },
  limit: 50,
  offset: 0,
};

const dispute: FinancialDispute = {
  id: "dispute-1",
  organization_id: "org-1",
  booking_id: "booking-1",
  release_id: "release-1",
  amount_cents: 40000,
  status: "OPEN",
  deadline_at: "2026-12-19T19:00:00Z",
  reason: "Valor divergente",
  evidence: "Comprovante interno",
  decision_reason: null,
  decided_by: null,
  decided_at: null,
  created_by: "user-1",
  created_at: "2026-12-16T20:00:00Z",
  updated_at: "2026-12-16T20:00:00Z",
};

const bookingFinancial: BookingFinancialResponse = {
  booking_id: "booking-1",
  pricing: {
    venue_price_cents: 40000,
    fee_cents: 8000,
    fee_percent_applied: 2000,
    total_cents: 48000,
    pricing_version: "adr0049_v1",
  },
  release: pendingReceivable,
  dispute,
  fiscal_document: {
    id: "fiscal-1",
    status: "pending_manual",
    amount_cents: 40000,
    number: null,
    provider_ref: null,
    issued_at: null,
  },
  ledger: [statementEntry],
  refunds: [],
};

function jsonResponse(body: unknown, status = 200, requestId?: string): Response {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (requestId) headers["X-Request-ID"] = requestId;
  return new Response(JSON.stringify(body), { status, headers });
}

function stubApi(
  options: {
    summary?: OrganizationFinancialSummary;
    receivables?: Receivable[];
    statement?: FinancialStatementEntry[];
    commission?: CommissionResponse;
    disputes?: FinancialDispute[];
    receivablesError?: { status: number; code: string };
  } = {},
) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/financial/summary")) {
      return jsonResponse(options.summary ?? summary);
    }
    if (url.includes("/financial/receivables")) {
      if (options.receivablesError) {
        return jsonResponse(
          { detail: { code: options.receivablesError.code } },
          options.receivablesError.status,
          "req-auth-1",
        );
      }
      const receivables = options.receivables ?? [pendingReceivable, releasedReceivable];
      return jsonResponse({
        receivables,
        total: receivables.length,
        limit: 50,
        offset: 0,
      });
    }
    if (url.includes("/financial/commission")) {
      return jsonResponse(options.commission ?? commission);
    }
    if (url.includes("/financial/statement")) {
      const entries = options.statement ?? [statementEntry, releaseEntry];
      return jsonResponse({ entries, total: entries.length, limit: 50, offset: 0 });
    }
    if (url.includes("/financial/disputes")) {
      const disputes = options.disputes ?? [dispute];
      return jsonResponse({ disputes, total: disputes.length, limit: 50, offset: 0 });
    }
    if (url.includes("/bookings/booking-1/financial")) {
      return jsonResponse(bookingFinancial);
    }
    return jsonResponse({ detail: { code: "not_found" } }, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderPanel(org: Organization = organization) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const view = render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <FinancialPanel organization={org} />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { ...view, queryClient };
}

describe("FinancialPanel — ledger em reais", () => {
  it("separa a comissão do JOGA do valor do fornecedor", async () => {
    stubApi();
    renderPanel();

    expect((await screen.findAllByText("Comissão do JOGA")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Cobrança total")).toBeInTheDocument();
    expect(screen.getAllByText(money(8000)).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Valor do fornecedor").length).toBeGreaterThan(0);
    expect(screen.getAllByText(money(40000)).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/não é receita do JOGA/i).length).toBeGreaterThan(0);
  });

  it("mostra composição, comprovante simulado e prazo de contestação no repasse", async () => {
    stubApi();
    renderPanel();

    expect(
      await screen.findByText("simulated:release-2 (comprovante simulado)"),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/Contestação até/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Espaço/).length).toBeGreaterThan(0);
  });

  it("envia o filtro de status dos repasses ao servidor", async () => {
    const fetchMock = stubApi();
    const user = userEvent.setup();
    renderPanel();

    await screen.findByText("simulated:release-2 (comprovante simulado)");
    await user.click(screen.getByRole("button", { name: "Repassados" }));

    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url]) => String(url).includes("status=RELEASED"))).toBe(
        true,
      ),
    );
  });

  it("exibe apenas os tipos de lançamento do contrato, sem CHARGE_CREATED", async () => {
    stubApi();
    renderPanel();

    expect(await screen.findByText("Pagamento confirmado — parte da quadra")).toBeInTheDocument();
    expect(screen.getByText("Repasse ao fornecedor")).toBeInTheDocument();
    expect(screen.queryByText("Cobrança criada")).not.toBeInTheDocument();
    expect(screen.queryByText("payment-1")).not.toBeInTheDocument();
  });

  it("filtra a comissão por período com from/to ISO", async () => {
    const fetchMock = stubApi();
    renderPanel();

    await screen.findByText("Comissão do JOGA");
    fireEvent.change(screen.getByLabelText("De"), { target: { value: "2026-11-01" } });
    fireEvent.change(screen.getByLabelText("Até"), { target: { value: "2026-11-30" } });
    const call = await waitFor(() => {
      const found = fetchMock.mock.calls.find(([url]) => {
        const candidate = new URL(String(url), "http://localhost");
        return (
          candidate.pathname.includes("/financial/commission") &&
          candidate.searchParams.has("from") &&
          candidate.searchParams.has("to")
        );
      });
      expect(found).toBeDefined();
      return found as unknown as [RequestInfo | URL, RequestInit | undefined];
    });
    const params = new URL(String(call[0]), "http://localhost").searchParams;
    const from = params.get("from");
    const to = params.get("to");
    expect(from?.startsWith("2026-11-01T")).toBe(true);
    expect(to).not.toBeNull();
    const toDate = new Date(to ?? "");
    expect([toDate.getFullYear(), toDate.getMonth() + 1, toDate.getDate()]).toEqual([2026, 11, 30]);
    expect(toDate.getTime()).toBeGreaterThan(new Date(from ?? "").getTime());
  });

  it("mostra prazo e decisão auditável da contestação", async () => {
    stubApi({
      disputes: [
        {
          ...dispute,
          status: "REJECTED",
          decided_by: "operator-1",
          decided_at: "2026-12-17T12:00:00Z",
          decision_reason: "Valores conferem com o ledger",
        },
      ],
    });
    renderPanel();

    expect(await screen.findByText(/prazo/)).toBeInTheDocument();
    expect(screen.getByText(/Valores conferem com o ledger/)).toBeInTheDocument();
  });
  it("abre o detalhe financeiro da reserva com NFS-e placeholder", async () => {
    stubApi();
    const user = userEvent.setup();
    renderPanel();

    const buttons = await screen.findAllByRole("button", { name: "Ver detalhe financeiro" });
    await user.click(buttons[0]);

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Composição da reserva")).toBeInTheDocument();
    expect(within(dialog).getAllByText(money(40000)).length).toBeGreaterThan(0);
    expect(within(dialog).getAllByText(money(8000)).length).toBeGreaterThan(0);
    expect(within(dialog).getAllByText(money(48000)).length).toBeGreaterThan(0);
    expect(within(dialog).getByText("Intenção registrada — sem emissão")).toBeInTheDocument();
    expect(within(dialog).getByText("Sem comprovante enquanto pendente")).toBeInTheDocument();
  });

  it("mostra erro de isolamento por organização sem exibir repasses", async () => {
    stubApi({ receivablesError: { status: 404, code: "organization_not_found" } });
    renderPanel();

    expect(
      (await screen.findAllByText("Organização não encontrada ou fora do seu acesso.")).length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText("req-auth-1").length).toBeGreaterThan(0);
    expect(
      screen.queryByText("simulated:release-2 (comprovante simulado)"),
    ).not.toBeInTheDocument();
  });

  it("busca o financeiro de outra organização ao trocar o escopo", async () => {
    const fetchMock = stubApi();
    const { rerender, queryClient } = renderPanel();
    await screen.findByText("Comissão do JOGA");

    const other = { ...organization, id: "org-2", name: "Arena Copacabana" };
    rerender(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <FinancialPanel organization={other} />
        </ToastProvider>
      </QueryClientProvider>,
    );

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) =>
          String(url).includes("/organizations/org-2/financial/summary"),
        ),
      ).toBe(true),
    );
  });
});
