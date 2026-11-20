import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "../../components/ui/Toast";
import { AuthContext } from "../../lib/auth-context";
import type { AdminPublicVenue, AdminPublicVenueDetail, AdminVenueAvailability } from "../../types";
import { AdminPublicVenuesPage } from "./AdminPublicVenuesPage";

const venue: AdminPublicVenue = {
  id: "venue-1",
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
};

const venueDetail: AdminPublicVenueDetail = {
  ...venue,
  spaces: [
    {
      id: "space-1",
      venue_id: "venue-1",
      name: "Quadra 1",
      description: null,
      is_covered: false,
      sport_id: "sport-1",
      format_id: "format-1",
      price_cents: 12_000,
      status: "active",
    },
  ],
};

const inactiveVenue: AdminPublicVenue = { ...venue, status: "inactive" };

const availabilityOne: AdminVenueAvailability = {
  id: "availability-1",
  space_id: "space-1",
  weekday: 1,
  start_time: "08:00",
  end_time: "22:00",
  price_cents: 12_000,
  slot_minutes: 60,
};

const availabilityTwo: AdminVenueAvailability = {
  ...availabilityOne,
  id: "availability-2",
  weekday: 3,
  start_time: "09:00",
  end_time: "12:00",
};

interface StubOptions {
  venues?: AdminPublicVenue[];
  total?: number;
  pageSize?: number;
  listError?: { status: number; code: string };
  spaceError?: { status: number; code: string };
  availability?: AdminVenueAvailability[];
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

type FetchMock = ReturnType<typeof vi.fn>;

interface Call {
  path: string;
  method: string;
  search: URLSearchParams;
  body: Record<string, unknown> | null;
}

function calls(fetchMock: FetchMock): Call[] {
  return fetchMock.mock.calls.map((raw) => {
    const [input, init] = raw as [RequestInfo | URL, RequestInit | undefined];
    const url = new URL(String(input), "http://joga.local");
    return {
      path: url.pathname,
      method: (init?.method ?? "GET").toUpperCase(),
      search: url.searchParams,
      body: init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : null,
    };
  });
}

async function waitForCall(fetchMock: FetchMock, method: string, path: string): Promise<Call> {
  let match: Call | undefined;
  await waitFor(() => {
    match = calls(fetchMock).find((call) => call.method === method && call.path === path);
    expect(match).toBeTruthy();
  });
  if (!match) throw new Error(`Chamada ${method} ${path} não encontrada`);
  return match;
}

function stubApi(options: StubOptions = {}): FetchMock {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://joga.local");
    const method = (init?.method ?? "GET").toUpperCase();
    const path = url.pathname;

    if (path === "/api/v1/admin/venues" && method === "GET") {
      if (options.listError) {
        return jsonResponse({ detail: { code: options.listError.code } }, options.listError.status);
      }
      return jsonResponse({
        venues: options.venues ?? [venue],
        total: options.total ?? (options.venues ?? [venue]).length,
        page: Number(url.searchParams.get("page") ?? "1"),
        page_size: options.pageSize ?? 20,
      });
    }

    if (path === "/api/v1/sports" && method === "GET") {
      return jsonResponse({
        sports: [
          {
            id: "sport-1",
            slug: "futebol",
            name: "Futebol",
            formats: [{ id: "format-1", slug: "futebol-5x5", name: "Futebol 5x5" }],
          },
        ],
      });
    }

    if (path === "/api/v1/pricing/bands" && method === "GET") {
      return jsonResponse({
        bands: [
          {
            id: "band-1",
            code: "economica_dia",
            label: "Econômica dia",
            max_price_cents: 30_000,
            version: 1,
          },
        ],
      });
    }

    if (path.startsWith("/api/v1/geo/postal-codes/") && method === "GET") {
      return jsonResponse({
        postal_code: "20000000",
        street: "Rua do CEP",
        neighborhood: "Centro",
        city: "Rio de Janeiro",
        state: "RJ",
        country: "BR",
        latitude: -22.91,
        longitude: -43.18,
        precision: "street",
        source: "brasilapi",
        resolved_at: "2026-11-20T12:00:00Z",
      });
    }

    if (path === "/api/v1/admin/venues" && method === "POST") {
      return jsonResponse({ ...venue, id: "venue-1", status: "inactive", spaces_count: 0 });
    }

    if (path === "/api/v1/admin/venues/venue-1" && method === "GET") {
      return jsonResponse(venueDetail);
    }

    if (path === "/api/v1/admin/venues/venue-1" && method === "PATCH") {
      return jsonResponse(venue);
    }

    if (path === "/api/v1/admin/venues/venue-1/spaces" && method === "GET") {
      return jsonResponse(venueDetail.spaces);
    }

    if (path === "/api/v1/admin/venues/venue-1/spaces" && method === "POST") {
      if (options.spaceError) {
        return jsonResponse(
          { detail: { code: options.spaceError.code } },
          options.spaceError.status,
        );
      }
      return jsonResponse(venueDetail.spaces[0]);
    }

    if (path === "/api/v1/admin/venues/venue-1/spaces/space-1" && method === "PATCH") {
      return jsonResponse(venueDetail.spaces[0]);
    }

    if (path === "/api/v1/admin/venues/venue-1/availability" && method === "GET") {
      return jsonResponse(options.availability ?? []);
    }

    if (path === "/api/v1/admin/venues/venue-1/availability" && method === "POST") {
      return jsonResponse({
        id: "availability-1",
        space_id: "space-1",
        weekday: 1,
        start_time: "08:00",
        end_time: "22:00",
        price_cents: 12_000,
        slot_minutes: 60,
      });
    }

    if (path === "/api/v1/admin/venues/venue-1/availability/availability-1" && method === "PATCH") {
      return jsonResponse({
        id: "availability-1",
        space_id: "space-1",
        weekday: 1,
        start_time: "08:00",
        end_time: "22:00",
        price_cents: 12_000,
        slot_minutes: 60,
      });
    }

    if (
      path === "/api/v1/admin/venues/venue-1/availability/availability-1" &&
      method === "DELETE"
    ) {
      return new Response(null, { status: 204 });
    }

    if (
      path === "/api/v1/admin/venues/venue-1/availability/availability-2" &&
      method === "DELETE"
    ) {
      return new Response(null, { status: 204 });
    }

    if (path === "/api/v1/admin/venues/venue-1/business-hours" && method === "GET") {
      return jsonResponse([]);
    }

    if (path === "/api/v1/admin/venues/venue-1/business-hours" && method === "POST") {
      return jsonResponse({ id: "hours-1", weekday: 1, opens_at: "06:00", closes_at: "23:00" });
    }

    if (path === "/api/v1/admin/venues/venue-1/business-hours/hours-1" && method === "PATCH") {
      return jsonResponse({ id: "hours-1", weekday: 1, opens_at: "06:00", closes_at: "23:00" });
    }

    if (path === "/api/v1/admin/venues/venue-1/business-hours/hours-1" && method === "DELETE") {
      return new Response(null, { status: 204 });
    }

    if (path.endsWith("/activate") && method === "POST") {
      return jsonResponse({ ...venue, status: "active" });
    }

    if (path.endsWith("/deactivate") && method === "POST") {
      return jsonResponse({ ...venue, status: "inactive" });
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
        <MemoryRouter initialEntries={["/admin/venues"]}>
          <AuthContext.Provider
            value={{
              user: { id: "admin-1", status: "active" },
              capabilities: ["platform.admin"],
              loading: false,
              sessionExpired: false,
              signIn: vi.fn(),
              signOut: vi.fn(),
            }}
          >
            <AdminPublicVenuesPage />
          </AuthContext.Provider>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

async function openCreate() {
  await screen.findByText("Arena Pública");
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Nova quadra pública" }));
  return user;
}

async function fillVenueData(
  user: ReturnType<typeof userEvent.setup>,
  options: { withCoordinates?: boolean } = {},
) {
  await user.type(screen.getByLabelText("Nome da quadra"), "Arena Nova");
  await user.type(screen.getByLabelText("Cidade"), "Niterói");
  await user.type(screen.getByLabelText("UF"), "RJ");
  await user.type(screen.getByLabelText("Endereço"), "Rua Nova, 100");
  await user.type(screen.getByLabelText("Motivo"), "Abertura de quadra pública");
  if (options.withCoordinates !== false) {
    await user.type(screen.getByLabelText("Latitude"), "-22.88");
    await user.type(screen.getByLabelText("Longitude"), "-43.10");
  }
}

async function fillSpace(
  user: ReturnType<typeof userEvent.setup>,
  options: { active?: boolean } = {},
) {
  await user.click(screen.getByRole("tab", { name: "2. Espaços" }));
  await screen.findByRole("option", { name: "Futebol" });
  await user.type(screen.getByLabelText("Nome do espaço"), "Quadra Central");
  await user.selectOptions(screen.getByLabelText("Modalidade"), "sport-1");
  await user.selectOptions(screen.getByLabelText("Formato"), "format-1");
  await user.type(screen.getByLabelText("Preço do espaço"), "120,00");
  if (options.active === false) {
    await user.selectOptions(screen.getByLabelText("Status"), "inactive");
  }
}

describe("AdminPublicVenuesPage", () => {
  it("lista vazia e paginação", async () => {
    const fetchMock = stubApi({ total: 45, pageSize: 20 });
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText("Arena Pública")).toBeInTheDocument();
    expect(screen.getByText("Mostrando 1–20 de 45")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Próxima" }));
    await waitFor(() =>
      expect(
        calls(fetchMock).some(
          (call) => call.path === "/api/v1/admin/venues" && call.search.get("page") === "2",
        ),
      ).toBe(true),
    );
  });

  it("mostra estado vazio", async () => {
    stubApi({ venues: [] });
    renderPage();

    expect(await screen.findByText("Nenhuma quadra pública")).toBeInTheDocument();
  });

  it("mostra 403 com mensagem própria", async () => {
    stubApi({ listError: { status: 403, code: "forbidden" } });
    renderPage();

    expect(await screen.findByText("Acesso restrito")).toBeInTheDocument();
    expect(
      screen.getByText("Sua conta não tem permissão de administração da plataforma."),
    ).toBeInTheDocument();
  });

  it("mostra o selo Pública na prévia", async () => {
    stubApi();
    renderPage();
    const user = await openCreate();

    await user.click(screen.getByRole("tab", { name: "4. Prévia" }));
    expect(screen.getByText("Pública")).toBeInTheDocument();
  });

  it("bloqueia criação sem coordenadas com geocoding_required", async () => {
    const fetchMock = stubApi();
    renderPage();
    const user = await openCreate();

    await fillVenueData(user, { withCoordinates: false });
    await fillSpace(user);
    await user.click(screen.getByRole("tab", { name: "4. Prévia" }));
    await user.click(screen.getByRole("button", { name: "Criar e publicar" }));

    expect(
      await screen.findByText(
        "Informe o CEP com coordenadas ou preencha latitude e longitude antes de publicar.",
      ),
    ).toBeInTheDocument();
    expect(
      calls(fetchMock).some(
        (call) => call.method === "POST" && call.path === "/api/v1/admin/venues",
      ),
    ).toBe(false);
  });

  it("bloqueia criação sem espaço ativo com venue_not_publishable", async () => {
    const fetchMock = stubApi();
    renderPage();
    const user = await openCreate();

    await fillVenueData(user);
    await fillSpace(user, { active: false });
    await user.click(screen.getByRole("tab", { name: "4. Prévia" }));
    await user.click(screen.getByRole("button", { name: "Criar e publicar" }));

    expect(
      await screen.findByText("A quadra precisa de pelo menos um espaço ativo para ser publicada."),
    ).toBeInTheDocument();
    expect(
      calls(fetchMock).some(
        (call) => call.method === "POST" && call.path === "/api/v1/admin/venues",
      ),
    ).toBe(false);
  });

  it("trata pricing_not_configured na criação do espaço", async () => {
    const fetchMock = stubApi({
      spaceError: { status: 422, code: "pricing_not_configured" },
    });
    renderPage();
    const user = await openCreate();

    await fillVenueData(user);
    await fillSpace(user);
    await user.click(screen.getByRole("tab", { name: "4. Prévia" }));
    await user.click(screen.getByRole("button", { name: "Criar e publicar" }));

    expect(
      await screen.findByText(
        "O preço ainda não está configurado nas seis faixas. Configure o preço antes de salvar ou publicar.",
      ),
    ).toBeInTheDocument();
    expect(calls(fetchMock).some((call) => call.path.endsWith("/activate"))).toBe(false);
  });

  it("cria, configura agenda e publica a quadra", async () => {
    const fetchMock = stubApi();
    renderPage();
    const user = await openCreate();

    await fillVenueData(user);
    await fillSpace(user);
    await user.click(screen.getByRole("tab", { name: "4. Prévia" }));
    await user.click(screen.getByRole("button", { name: "Criar e publicar" }));

    expect(await screen.findByText("Quadra pública publicada")).toBeInTheDocument();

    const createCall = await waitForCall(fetchMock, "POST", "/api/v1/admin/venues");
    expect(createCall.body).toMatchObject({
      name: "Arena Nova",
      city: "Niterói",
      state: "RJ",
      address_line: "Rua Nova, 100",
      latitude: -22.88,
      longitude: -43.1,
      is_public: true,
      reason: "Abertura de quadra pública",
    });

    const spaceCall = await waitForCall(fetchMock, "POST", "/api/v1/admin/venues/venue-1/spaces");
    expect(spaceCall.body).toMatchObject({
      name: "Quadra Central",
      sport_id: "sport-1",
      format_id: "format-1",
      price_cents: 12_000,
      status: "active",
      reason: "Abertura de quadra pública",
    });

    const availabilityCall = await waitForCall(
      fetchMock,
      "POST",
      "/api/v1/admin/venues/venue-1/availability",
    );
    expect(availabilityCall.body).toMatchObject({
      space_id: "space-1",
      weekday: 1,
      start_time: "08:00",
      end_time: "22:00",
      price_cents: 12_000,
      reason: "Abertura de quadra pública",
    });
    const hoursCall = await waitForCall(
      fetchMock,
      "POST",
      "/api/v1/admin/venues/venue-1/business-hours",
    );
    expect(hoursCall.body).toMatchObject({
      weekday: 1,
      opens_at: "06:00",
      closes_at: "23:00",
      reason: "Abertura de quadra pública",
    });
    const activateCall = await waitForCall(
      fetchMock,
      "POST",
      "/api/v1/admin/venues/venue-1/activate",
    );
    expect(activateCall.body).toEqual({ reason: "Abertura de quadra pública" });
  }, 20_000);

  it("busca CEP e preenche coordenadas", async () => {
    stubApi();
    renderPage();
    const user = await openCreate();

    await user.type(screen.getByLabelText("CEP"), "20000000");
    await user.click(screen.getByRole("button", { name: "Buscar CEP" }));

    await waitFor(() => expect(screen.getByLabelText("Latitude")).toHaveValue("-22.91"));
    expect(screen.getByLabelText("Longitude")).toHaveValue("-43.18");
    expect(screen.getByLabelText("Cidade")).toHaveValue("Rio de Janeiro");
  });

  it("desativa com motivo", async () => {
    const fetchMock = stubApi();
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Arena Pública");
    await user.click(screen.getByRole("button", { name: "Desativar" }));
    await user.type(screen.getByLabelText("Motivo"), "Manutenção");
    await user.click(screen.getByRole("button", { name: "Desativar quadra" }));

    expect(await screen.findByText("Quadra desativada")).toBeInTheDocument();
    const call = await waitForCall(fetchMock, "POST", "/api/v1/admin/venues/venue-1/deactivate");
    expect(call.body).toEqual({ reason: "Manutenção" });
  });

  it("publica com motivo", async () => {
    const fetchMock = stubApi({ venues: [inactiveVenue] });
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Arena Pública");
    await user.click(screen.getByRole("button", { name: "Publicar" }));
    await user.type(screen.getByLabelText("Motivo"), "Reabertura");
    await user.click(screen.getByRole("button", { name: "Publicar quadra" }));

    expect(await screen.findByText("Quadra publicada")).toBeInTheDocument();
    const call = await waitForCall(fetchMock, "POST", "/api/v1/admin/venues/venue-1/activate");
    expect(call.body).toEqual({ reason: "Reabertura" });
  });

  it("usa active_spaces_count no selo da descoberta", async () => {
    stubApi({ venues: [{ ...venue, spaces_count: 2, active_spaces_count: 0 }] });
    renderPage();

    expect(await screen.findByText("Arena Pública")).toBeInTheDocument();
    expect(screen.getByText("Fora da descoberta")).toBeInTheDocument();
    expect(screen.queryByText("Na descoberta")).not.toBeInTheDocument();
  });

  it("edita quadra pública, carrega janelas por espaço e remove uma janela", async () => {
    const fetchMock = stubApi({ availability: [availabilityOne, availabilityTwo] });
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Editar" }));
    const name = await screen.findByLabelText("Nome da quadra");
    expect(name).toHaveValue("Arena Pública");
    await user.type(screen.getByLabelText("Motivo"), "Ajuste de agenda");

    await user.click(screen.getByRole("tab", { name: "3. Agenda" }));
    const starts = await screen.findAllByLabelText("Início");
    expect(starts).toHaveLength(2);
    expect(starts[0]).toHaveValue("08:00");
    expect(starts[1]).toHaveValue("09:00");

    const secondWindow = starts[1].closest(".form-row");
    expect(secondWindow).not.toBeNull();
    await user.click(within(secondWindow as HTMLElement).getByRole("button", { name: "Remover" }));
    expect(screen.getAllByLabelText("Início")).toHaveLength(1);

    await user.click(screen.getByRole("tab", { name: "4. Prévia" }));
    await user.click(screen.getByRole("button", { name: "Salvar alterações" }));

    expect(await screen.findByText("Quadra pública salva")).toBeInTheDocument();

    expect(
      calls(fetchMock).some(
        (call) =>
          call.method === "GET" &&
          call.path === "/api/v1/admin/venues/venue-1/availability" &&
          call.search.get("space_id") === "space-1",
      ),
    ).toBe(true);

    const deleteCall = await waitForCall(
      fetchMock,
      "DELETE",
      "/api/v1/admin/venues/venue-1/availability/availability-2",
    );
    expect(deleteCall.search.get("space_id")).toBe("space-1");
    expect(deleteCall.search.get("reason")).toBe("Ajuste de agenda");

    expect(
      calls(fetchMock).some(
        (call) =>
          call.method === "DELETE" &&
          call.path === "/api/v1/admin/venues/venue-1/availability/availability-1",
      ),
    ).toBe(false);
  }, 20_000);
});
