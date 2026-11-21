import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "../../components/ui/Toast";
import type { AdminVenueDetail } from "../../types";
import { AdminVenueDetailPage } from "./AdminVenueDetailPage";

const venue: AdminVenueDetail = {
  id: "venue-1",
  organization_id: "org-platform",
  organization_name: "JOGA Público",
  organization_is_platform: true,
  organization_status: "active",
  name: "Arena Pública",
  city: "Rio de Janeiro",
  state: "RJ",
  address_line: "Rua das Quadras, 10",
  postal_code: "20000000",
  latitude: -22.9068,
  longitude: -43.1729,
  is_public: true,
  status: "active",
  spaces_count: 1,
  active_spaces_count: 1,
  created_at: "2026-11-01T12:00:00Z",
  updated_at: "2026-11-02T12:00:00Z",
  spaces: [
    {
      id: "space-1",
      venue_id: "venue-1",
      name: "Quadra 1",
      description: null,
      is_covered: true,
      sport_id: "sport-1",
      format_id: "format-1",
      price_cents: 12000,
      status: "active",
      created_at: "2026-11-01T12:00:00Z",
      updated_at: "2026-11-01T12:00:00Z",
    },
  ],
};

const sports = {
  sports: [
    {
      id: "sport-1",
      slug: "futebol",
      name: "Futebol",
      formats: [{ id: "format-1", slug: "futebol-5x5", name: "Futebol 5x5" }],
    },
  ],
};

const bands = {
  bands: [
    { id: "band-1", code: "economica", label: "Econômica", max_price_cents: 50000, version: 1 },
  ],
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

interface Call {
  path: string;
  method: string;
  body: Record<string, unknown> | null;
}

function calls(fetchMock: ReturnType<typeof vi.fn>): Call[] {
  return fetchMock.mock.calls.map((raw) => {
    const [input, init] = raw as [RequestInfo | URL, RequestInit | undefined];
    return {
      path: new URL(String(input), "http://joga.local").pathname,
      method: (init?.method ?? "GET").toUpperCase(),
      body: init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : null,
    };
  });
}

function stubApi() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(String(input), "http://joga.local").pathname;
    const method = (init?.method ?? "GET").toUpperCase();
    if (path === "/api/v1/admin/venues/venue-1" && method === "GET") {
      return jsonResponse(venue);
    }
    if (path === "/api/v1/sports") return jsonResponse(sports);
    if (path === "/api/v1/pricing/bands") return jsonResponse(bands);
    if (path === "/api/v1/admin/venues/venue-1/availability" && method === "GET") {
      return jsonResponse([]);
    }
    if (path === "/api/v1/admin/venues/venue-1/availability" && method === "POST") {
      return jsonResponse(
        {
          id: "availability-1",
          space_id: "space-1",
          weekday: 1,
          start_time: "08:00:00",
          end_time: "22:00:00",
          price_cents: 12000,
          slot_minutes: 60,
        },
        201,
      );
    }
    if (path === "/api/v1/admin/venues/venue-1/business-hours" && method === "GET") {
      return jsonResponse([]);
    }
    if (path === "/api/v1/admin/venues/venue-1/business-hours" && method === "POST") {
      return jsonResponse(
        { id: "hours-1", weekday: 1, opens_at: "06:00:00", closes_at: "23:00:00" },
        201,
      );
    }
    if (path === "/api/v1/admin/venues/venue-1/spaces/space-1" && method === "PATCH") {
      return jsonResponse({ ...venue.spaces[0], name: "Quadra Central" });
    }
    if (path === "/api/v1/organizations/org-platform/venues/venue-1/photos") {
      return jsonResponse({ photos: [], can_review: true });
    }
    return jsonResponse({ detail: { code: "not_found" } }, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/admin/venues/venue-1"]}>
          <Routes>
            <Route path="/admin/venues/:venueId" element={<AdminVenueDetailPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("AdminVenueDetailPage", () => {
  it("lista os espaços e salva a edição com motivo", async () => {
    const fetchMock = stubApi();
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByRole("heading", { name: "Arena Pública" })).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Editar espaço Quadra 1" }));

    const name = screen.getByLabelText("Nome do espaço");
    await user.clear(name);
    await user.type(name, "Quadra Central");
    await user.type(screen.getByLabelText("Motivo"), "Ajuste de nome do espaço");
    await user.click(screen.getByRole("button", { name: "Salvar espaço" }));

    expect(await screen.findByText("Espaço salvo")).toBeInTheDocument();
    await waitFor(() => {
      const call = calls(fetchMock).find(
        (item) =>
          item.method === "PATCH" && item.path === "/api/v1/admin/venues/venue-1/spaces/space-1",
      );
      expect(call).toBeTruthy();
      expect(call?.body).toMatchObject({
        name: "Quadra Central",
        sport_id: "sport-1",
        format_id: "format-1",
        price_cents: 12000,
        status: "active",
        reason: "Ajuste de nome do espaço",
      });
    });
  });

  it("cria janela de agenda para o espaço selecionado", async () => {
    const fetchMock = stubApi();
    const user = userEvent.setup();
    renderPage();

    await screen.findByRole("heading", { name: "Arena Pública" });
    await user.click(screen.getByRole("tab", { name: "Agenda" }));

    expect(await screen.findByText("Disponibilidade semanal")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Preço da janela"), "120,00");
    const reasons = screen.getAllByLabelText("Motivo");
    await user.type(reasons[0] as HTMLElement, "Abertura da agenda");
    await user.click(screen.getByRole("button", { name: "Adicionar janela" }));

    expect(await screen.findByText("Janela salva")).toBeInTheDocument();
    await waitFor(() => {
      const call = calls(fetchMock).find(
        (item) =>
          item.method === "POST" && item.path === "/api/v1/admin/venues/venue-1/availability",
      );
      expect(call?.body).toMatchObject({
        space_id: "space-1",
        weekday: 1,
        start_time: "08:00:00",
        end_time: "22:00:00",
        price_cents: 12000,
        slot_minutes: 60,
        reason: "Abertura da agenda",
      });
    });
  });

  it("abre as fotos da quadra da plataforma", async () => {
    const fetchMock = stubApi();
    const user = userEvent.setup();
    renderPage();

    await screen.findByRole("heading", { name: "Arena Pública" });
    await user.click(screen.getByRole("tab", { name: /Fotos/ }));

    expect(await screen.findByText("Nenhuma foto")).toBeInTheDocument();
    expect(
      calls(fetchMock).some(
        (item) =>
          item.method === "GET" &&
          item.path === "/api/v1/organizations/org-platform/venues/venue-1/photos",
      ),
    ).toBe(true);
  });

  it("mostra a quadra sem oferecer fotos de organização parceira", async () => {
    stubApi();
    const partner = {
      ...venue,
      organization_id: "org-partner",
      organization_name: "Arena Tijuca",
      organization_is_platform: false,
      spaces: [],
    };
    vi.mocked(fetch).mockImplementation(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), "http://joga.local").pathname;
      if (path === "/api/v1/admin/venues/venue-1") return jsonResponse(partner);
      if (path === "/api/v1/sports") return jsonResponse(sports);
      if (path === "/api/v1/pricing/bands") return jsonResponse(bands);
      if (path.endsWith("/availability")) return jsonResponse([]);
      if (path.endsWith("/business-hours")) return jsonResponse([]);
      return jsonResponse({ detail: { code: "not_found" } }, 404);
    });

    renderPage();
    await screen.findByRole("heading", { name: "Arena Pública" });
    expect(screen.queryByRole("tab", { name: /Fotos/ })).not.toBeInTheDocument();
    expect(screen.getByText("Nenhum espaço")).toBeInTheDocument();
  });
});
