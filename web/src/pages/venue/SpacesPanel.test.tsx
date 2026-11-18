import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "../../components/ui/Toast";
import type { Organization, Venue, VenueSpace } from "../../types";
import { SpacesPanel } from "./SpacesPanel";

const organization: Organization = {
  id: "org-1",
  name: "Arena Tijuca",
  status: "active",
  role: "OWNER",
  payout_ready: true,
  payout_status: "active",
  pix_key_type: "cnpj",
  pix_key_masked: "****0001",
  created_at: "2026-11-01T12:00:00Z",
  updated_at: "2026-11-01T12:00:00Z",
};

const venue: Venue = {
  id: "venue-1",
  organization_id: "org-1",
  venue_id: null,
  name: "Arena Centro",
  city: "Rio de Janeiro",
  state: "RJ",
  address_line: null,
  latitude: -22.9,
  longitude: -43.2,
  postal_code: null,
  geocoding_source: null,
  geocoding_precision: "manual",
  geocoded_at: null,
  timezone: "America/Sao_Paulo",
  status: "active",
  created_at: "2026-11-01T12:00:00Z",
  updated_at: "2026-11-01T12:00:00Z",
};

const space: VenueSpace = {
  id: "space-1",
  venue_id: "venue-1",
  name: "Quadra 1",
  description: "Coberta",
  is_covered: true,
  status: "active",
  sports: [],
  created_at: "2026-11-01T12:00:00Z",
  updated_at: "2026-11-01T12:00:00Z",
};

const availability = {
  id: "availability-1",
  space_id: "space-1",
  weekday: 1,
  start_time: "18:00:00",
  end_time: "22:00:00",
  price_cents: 12000,
  slot_minutes: 60,
  band_id: null,
};

const businessHour = {
  id: "hour-1",
  weekday: 1,
  opens_at: "14:00:00",
  closes_at: "18:00:00",
};

const businessHourMorning = {
  id: "hour-2",
  weekday: 1,
  opens_at: "09:00:00",
  closes_at: "12:00:00",
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubApi() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.includes("/availability/availability-1") && init?.method === "PATCH") {
      return jsonResponse({ ...availability, price_cents: 15000 });
    }
    if (url.includes("/business-hours/hour-1") && init?.method === "PATCH") {
      return jsonResponse({ ...businessHour, opens_at: "10:00:00" });
    }
    if (url.includes("/spaces/space-1") && init?.method === "PATCH") {
      return jsonResponse({ ...space, name: "Quadra Central" });
    }
    if (url.endsWith("/availability")) {
      return jsonResponse({ availability: [availability] });
    }
    if (url.includes("/blackouts")) return jsonResponse({ blackouts: [] });
    if (url.endsWith("/business-hours")) {
      return jsonResponse({ business_hours: [businessHourMorning, businessHour] });
    }
    if (url.endsWith("/closures")) return jsonResponse({ closures: [] });
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
        <SpacesPanel
          organization={organization}
          venue={venue}
          spaces={[space]}
          sports={[]}
          bands={[]}
          selectedSpaceId="space-1"
          onSelectSpace={vi.fn()}
        />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("SpacesPanel — edição", () => {
  it("edita nome e cobertura da quadra", async () => {
    const fetchMock = stubApi();
    const user = userEvent.setup();
    renderPanel();

    await user.click(await screen.findByRole("button", { name: "Editar quadra" }));
    const dialog = await screen.findByRole("dialog");
    const name = within(dialog).getByLabelText("Nome");
    await user.clear(name);
    await user.type(name, "Quadra Central");
    await user.click(within(dialog).getByRole("button", { name: "Salvar alterações" }));

    expect(await screen.findByText("Quadra atualizada")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([url, init]) =>
            String(url).includes("/spaces/space-1") &&
            (init as RequestInit | undefined)?.method === "PATCH",
        ),
      ).toBe(true),
    );
  });

  it("edita a janela da agenda", async () => {
    const fetchMock = stubApi();
    const user = userEvent.setup();
    renderPanel();

    await user.click(await screen.findByRole("button", { name: "Editar" }));
    const dialog = await screen.findByRole("dialog");
    const price = within(dialog).getByLabelText("Preço da vaga");
    await user.clear(price);
    await user.type(price, "150,00");
    await user.click(within(dialog).getByRole("button", { name: "Salvar janela" }));

    expect(await screen.findByText("Janela atualizada")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([url, init]) =>
            String(url).includes("/availability/availability-1") &&
            (init as RequestInit | undefined)?.method === "PATCH",
        ),
      ).toBe(true),
    );
  });

  it("edita o expediente pelo PATCH sem apagar a janela", async () => {
    const fetchMock = stubApi();
    const user = userEvent.setup();
    renderPanel();

    await user.click(
      await screen.findByRole("button", {
        name: "Editar expediente de Segunda-feira (14:00–18:00)",
      }),
    );
    const dialog = await screen.findByRole("dialog");
    const opens = within(dialog).getByLabelText("Abre");
    await user.clear(opens);
    await user.type(opens, "15:00");
    await user.click(within(dialog).getByRole("button", { name: "Salvar expediente" }));

    expect(await screen.findByText("Expediente atualizado")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([url, init]) =>
            String(url).includes("/business-hours/hour-1") &&
            (init as RequestInit | undefined)?.method === "PATCH" &&
            String((init as RequestInit | undefined)?.body).includes('"opens_at":"15:00:00"'),
        ),
      ).toBe(true),
    );
  });

  it("bloqueia expediente sobreposto no cliente antes do envio", async () => {
    const fetchMock = stubApi();
    const user = userEvent.setup();
    renderPanel();

    await user.click(
      await screen.findByRole("button", {
        name: "Editar expediente de Segunda-feira (14:00–18:00)",
      }),
    );
    const dialog = await screen.findByRole("dialog");
    const opens = within(dialog).getByLabelText("Abre");
    await user.clear(opens);
    await user.type(opens, "11:00");
    await user.click(within(dialog).getByRole("button", { name: "Salvar expediente" }));

    expect(await screen.findByText(/Conflito com o expediente de 09:00–12:00/)).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url).includes("/business-hours/hour-1") &&
          (init as RequestInit | undefined)?.method === "PATCH",
      ),
    ).toBe(false);
  });
});
