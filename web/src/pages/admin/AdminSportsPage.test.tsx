import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "../../components/ui/Toast";
import { AuthContext } from "../../lib/auth-context";
import type { AdminPricingBandSuggestion, AdminSport, VisualCatalogResponse } from "../../types";
import { AdminSportsPage } from "./AdminSportsPage";

const sport: AdminSport = {
  id: "sport-1",
  slug: "futebol",
  name: "Futebol",
  icon_key: "icon-sport-futebol-5x5",
  sort_order: 10,
  active: true,
  formats: [
    {
      id: "format-1",
      slug: "futebol-5x5",
      name: "Futebol 5x5",
      team_size: 5,
      players_per_team: 5,
      total_participants: 10,
      duration_minutes: 60,
      period_count: 2,
      score_model: "goals",
      positions: ["Goleiro", "Fixo", "Ala", "Pivô"],
      active: true,
      version: 1,
      in_use: false,
    },
  ],
};

const inactiveSport: AdminSport = {
  ...sport,
  id: "sport-2",
  slug: "volei",
  name: "Vôlei",
  icon_key: "icon-sport-volei-6x6",
  active: false,
  formats: [{ ...sport.formats[0], id: "format-2", slug: "volei-6x6", name: "Vôlei 6x6" }],
};

const catalog: VisualCatalogResponse = {
  catalog_version: 1,
  items: [
    {
      key: "icon-sport-futebol-5x5",
      kind: "icon",
      name: "Futebol 5x5",
      asset_ref: "icons/futebol.svg",
      season: null,
      unlock_state: "free",
      active: true,
    },
    {
      key: "icon-sport-volei-6x6",
      kind: "icon",
      name: "Vôlei 6x6",
      asset_ref: "icons/volei.svg",
      season: null,
      unlock_state: "free",
      active: true,
    },
    {
      key: "icon-sport-antigo",
      kind: "icon",
      name: "Antigo",
      asset_ref: "icons/antigo.svg",
      season: null,
      unlock_state: "free",
      active: false,
    },
    {
      key: "frame-bronze",
      kind: "frame",
      name: "Moldura bronze",
      asset_ref: "frames/bronze.svg",
      season: null,
      unlock_state: "free",
      active: true,
    },
  ],
};

const bands: AdminPricingBandSuggestion[] = [
  {
    code: "economica_dia",
    label: "Econômica dia",
    max_price_cents: 12_000,
    tickets: 5,
    player_price_cents: 1_550,
    invariant_ok: true,
  },
  {
    code: "economica_noite",
    label: "Econômica noite",
    max_price_cents: 15_000,
    tickets: 6,
    player_price_cents: 1_860,
    invariant_ok: true,
  },
  {
    code: "padrao_dia",
    label: "Padrão dia",
    max_price_cents: 18_000,
    tickets: 7,
    player_price_cents: 2_170,
    invariant_ok: true,
  },
  {
    code: "padrao_noite",
    label: "Padrão noite",
    max_price_cents: 22_000,
    tickets: 9,
    player_price_cents: 2_790,
    invariant_ok: true,
  },
  {
    code: "coberta",
    label: "Coberta",
    max_price_cents: 26_000,
    tickets: 11,
    player_price_cents: 3_410,
    invariant_ok: true,
  },
  {
    code: "premium",
    label: "Premium",
    max_price_cents: 30_000,
    tickets: 12,
    player_price_cents: 3_720,
    invariant_ok: true,
  },
];

interface StubOptions {
  sports?: AdminSport[];
  sportsError?: { status: number; code: string };
  suggestError?: { status: number; code: string };
  visualError?: boolean;
  inUse?: boolean;
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

function findCall(fetchMock: FetchMock, method: string, path: string): Call | undefined {
  return calls(fetchMock).find((call) => call.method === method && call.path === path);
}

async function waitForCall(fetchMock: FetchMock, method: string, path: string): Promise<Call> {
  let match: Call | undefined;
  await waitFor(() => {
    match = findCall(fetchMock, method, path);
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

    if (path === "/api/v1/admin/sports" && method === "GET") {
      if (options.sportsError) {
        return jsonResponse(
          { detail: { code: options.sportsError.code } },
          options.sportsError.status,
        );
      }
      return jsonResponse({ sports: options.sports ?? [sport] });
    }

    if (path === "/api/v1/catalog/visual" && method === "GET") {
      if (options.visualError) return jsonResponse({ detail: { code: "request_failed" } }, 500);
      return jsonResponse(catalog);
    }

    if (path === "/api/v1/admin/pricing/suggest" && method === "GET") {
      if (options.suggestError) {
        return jsonResponse(
          { detail: { code: options.suggestError.code } },
          options.suggestError.status,
        );
      }
      return jsonResponse({
        team_size: Number(url.searchParams.get("team_size") ?? "5"),
        mode: url.searchParams.get("mode") ?? "standard",
        calibration_cents: 310,
        bands,
      });
    }

    if (path === "/api/v1/admin/pricing/band-tickets" && method === "PUT") {
      return jsonResponse({
        band_code: "economica_dia",
        team_size: 5,
        tickets: 8,
        player_price_cents: 2_480,
        mode: "standard",
        invariant_ok: true,
      });
    }

    if (path === "/api/v1/admin/sports" && method === "POST") {
      return jsonResponse({ ...sport, active: false });
    }

    if (path === "/api/v1/admin/sports/futebol" && method === "PATCH") {
      return jsonResponse(sport);
    }

    if (path.endsWith("/activate") && method === "POST") {
      return jsonResponse({ ...inactiveSport, active: true });
    }

    if (path.endsWith("/deactivate") && method === "POST") {
      return jsonResponse({ ...sport, active: false });
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
        <MemoryRouter initialEntries={["/admin/sports"]}>
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
            <AdminSportsPage />
          </AuthContext.Provider>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

async function openCreateForm() {
  await screen.findByText("Futebol");
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Novo esporte" }));
  await screen.findByRole("option", { name: /Futebol 5x5/ });
  return user;
}

async function fillSportData(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Nome"), "Futsal");
  await user.type(screen.getByLabelText("Slug"), "futsal");
  await user.selectOptions(screen.getByLabelText("Ícone"), "icon-sport-futebol-5x5");
}

async function fillFirstFormat(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Nome do formato"), "Futsal 5x5");
  await user.type(screen.getByLabelText("Slug do formato"), "futsal-5x5");
  await user.clear(screen.getByLabelText("Jogadores por equipe"));
  await user.type(screen.getByLabelText("Jogadores por equipe"), "5");
  await user.clear(screen.getByLabelText("Duração (min)"));
  await user.type(screen.getByLabelText("Duração (min)"), "40");
  await user.clear(screen.getByLabelText("Períodos"));
  await user.type(screen.getByLabelText("Períodos"), "2");
  await user.selectOptions(screen.getByLabelText("Modelo de pontuação"), "goals");
  await user.type(screen.getByLabelText("Posições"), "Goleiro, Fixo, Ala, Pivô");
  await user.type(screen.getByLabelText("Motivo"), "Abertura de catálogo");
}

describe("AdminSportsPage", () => {
  it("lista modalidades e mostra a prévia do formulário", async () => {
    stubApi();
    renderPage();
    const user = await openCreateForm();

    await fillSportData(user);
    await fillFirstFormat(user);

    expect(screen.getByText(/5x5 · 10 jogadores · 40 min · 2 período/)).toBeInTheDocument();
    expect(screen.getByText("Goleiro")).toBeInTheDocument();
    expect(screen.getByLabelText("Total de jogadores")).toHaveValue("10");
  }, 15_000);

  it("lista somente ícones ativos do catálogo visual", async () => {
    stubApi();
    renderPage();
    await openCreateForm();

    const select = screen.getByLabelText("Ícone");
    const options = within(select)
      .getAllByRole("option")
      .map((option) => option.textContent);
    expect(options).toContain("Futebol 5x5 — icon-sport-futebol-5x5");
    expect(options).toContain("Vôlei 6x6 — icon-sport-volei-6x6");
    expect(options).not.toContain("Antigo — icon-sport-antigo");
    expect(options).not.toContain("Moldura bronze — frame-bronze");
  });

  it("usa campo de texto com aviso quando o catálogo falha", async () => {
    stubApi({ visualError: true });
    renderPage();
    await screen.findByText("Futebol");
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Novo esporte" }));

    expect(await screen.findByText(/Catálogo de ícones indisponível/)).toBeInTheDocument();
    expect(screen.getByLabelText("Chave do ícone (icon_key)")).toBeInTheDocument();
  });

  it("cria um esporte com o contrato oficial", async () => {
    const fetchMock = stubApi();
    renderPage();
    const user = await openCreateForm();

    await fillSportData(user);
    await fillFirstFormat(user);
    await user.click(screen.getByRole("button", { name: "Criar esporte" }));

    expect(await screen.findByText("Esporte criado")).toBeInTheDocument();
    const call = await waitForCall(fetchMock, "POST", "/api/v1/admin/sports");
    expect(call.body).toEqual({
      name: "Futsal",
      slug: "futsal",
      icon_key: "icon-sport-futebol-5x5",
      sort_order: 0,
      reason: "Abertura de catálogo",
      formats: [
        {
          name: "Futsal 5x5",
          slug: "futsal-5x5",
          team_size: 5,
          players_per_team: 5,
          duration_minutes: 40,
          period_count: 2,
          score_model: "goals",
          positions: ["Goleiro", "Fixo", "Ala", "Pivô"],
        },
      ],
    });
  }, 15_000);

  it("bloqueia a criação quando o preço do formato não está configurado", async () => {
    const fetchMock = stubApi({
      suggestError: { status: 422, code: "pricing_not_configured" },
    });
    renderPage();
    const user = await openCreateForm();

    await fillSportData(user);
    await fillFirstFormat(user);
    await user.click(screen.getByRole("button", { name: "Criar esporte" }));

    expect(
      await screen.findByText(/O preço do formato 5x5 ainda não está configurado/),
    ).toBeInTheDocument();
    expect(findCall(fetchMock, "POST", "/api/v1/admin/sports")).toBeUndefined();
  }, 15_000);

  it("exige modo explícito para formato fora de 3x3, 5x5 e 6x6", async () => {
    stubApi();
    renderPage();
    const user = await openCreateForm();

    const teamSize = screen.getByLabelText("Jogadores por equipe");
    await user.clear(teamSize);
    await user.type(teamSize, "4");
    expect(screen.getByLabelText("Modo de preço")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Salvar tickets" })).not.toBeInTheDocument();
  });

  it("edita apenas os dados do esporte, sem simular formato", async () => {
    const fetchMock = stubApi();
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Futebol");
    await user.click(screen.getByRole("button", { name: "Editar" }));
    expect(screen.getByText("Edição de formato ainda não disponível.")).toBeInTheDocument();
    expect(screen.getByLabelText("Jogadores por equipe")).toBeDisabled();
    await user.clear(screen.getByLabelText("Nome"));
    await user.type(screen.getByLabelText("Nome"), "Futebol de campo");
    await user.type(screen.getByLabelText("Motivo"), "Correção de nome");
    await user.click(screen.getByRole("button", { name: "Salvar alterações" }));

    expect(await screen.findByText("Esporte atualizado")).toBeInTheDocument();
    const call = await waitForCall(fetchMock, "PATCH", "/api/v1/admin/sports/futebol");
    expect(call.body).toEqual({
      name: "Futebol de campo",
      icon_key: "icon-sport-futebol-5x5",
      sort_order: 10,
      reason: "Correção de nome",
    });
  }, 15_000);

  it("avisa quando o formato está em uso", async () => {
    stubApi({
      sports: [
        {
          ...sport,
          formats: [{ ...sport.formats[0], in_use: true }],
        },
      ],
    });
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Futebol");
    await user.click(screen.getByRole("button", { name: "Editar" }));
    expect(
      screen.getByText(
        "Formato em uso por reservas. Crie um novo formato para mudar o tamanho da equipe.",
      ),
    ).toBeInTheDocument();
  });

  it("desativa com motivo", async () => {
    const fetchMock = stubApi();
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Futebol");
    await user.click(screen.getByRole("button", { name: "Desativar" }));
    await user.type(screen.getByLabelText("Motivo"), "Temporada encerrada");
    await user.click(screen.getByRole("button", { name: "Desativar esporte" }));

    expect(await screen.findByText("Esporte desativado")).toBeInTheDocument();
    const call = await waitForCall(fetchMock, "POST", "/api/v1/admin/sports/futebol/deactivate");
    expect(call.body).toEqual({ reason: "Temporada encerrada" });
  });

  it("publica um esporte desativado com motivo", async () => {
    const fetchMock = stubApi({ sports: [inactiveSport] });
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Vôlei");
    await user.click(screen.getByRole("button", { name: "Publicar" }));
    await user.type(screen.getByLabelText("Motivo"), "Catálogo revisado");
    await user.click(screen.getByRole("button", { name: "Publicar esporte" }));

    expect(await screen.findByText("Esporte publicado")).toBeInTheDocument();
    const call = await waitForCall(fetchMock, "POST", "/api/v1/admin/sports/volei/activate");
    expect(call.body).toEqual({ reason: "Catálogo revisado" });
  });

  it("mostra as 6 faixas com k sugerido, invariante e preço por jogador", async () => {
    stubApi();
    renderPage();

    expect(await screen.findByText("Econômica dia")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Ajustar" })).toHaveLength(6);
    expect(screen.getAllByText("Cobre")).toHaveLength(6);
    expect(screen.getByText("R$ 15,50")).toBeInTheDocument();
  });

  it("exige modo explícito no bloco de preço para formato não padrão", async () => {
    const fetchMock = stubApi();
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Econômica dia");
    const teamSize = screen.getByLabelText("Equipe para preço");
    await user.clear(teamSize);
    await user.type(teamSize, "4");
    expect(screen.getByLabelText("Modo de preço")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Modo de preço"), "contingency");

    await waitFor(() =>
      expect(
        calls(fetchMock).some(
          (call) =>
            call.path === "/api/v1/admin/pricing/suggest" &&
            call.search.get("team_size") === "4" &&
            call.search.get("mode") === "contingency",
        ),
      ).toBe(true),
    );
  });

  it("salva um override válido com band_code, mode e motivo", async () => {
    const fetchMock = stubApi();
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Econômica dia");
    await user.click(screen.getAllByRole("button", { name: "Ajustar" })[0]);
    const tickets = screen.getByLabelText("Tickets por jogador (k)");
    await user.clear(tickets);
    await user.type(tickets, "8");
    await user.type(screen.getByLabelText("Motivo do override"), "Ajuste sazonal");
    expect(screen.getByRole("button", { name: "Salvar tickets" })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "Salvar tickets" }));
    await waitFor(() =>
      expect(findCall(fetchMock, "PUT", "/api/v1/admin/pricing/band-tickets")).toBeTruthy(),
    );

    expect(await screen.findByText("Tabela de tickets atualizada")).toBeInTheDocument();
    const call = await waitForCall(fetchMock, "PUT", "/api/v1/admin/pricing/band-tickets");
    expect(call.body).toEqual({
      band_code: "economica_dia",
      team_size: 5,
      tickets: 8,
      mode: "standard",
      reason: "Ajuste sazonal",
    });
  });

  it("bloqueia um override que viola o invariante", async () => {
    const fetchMock = stubApi();
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Econômica dia");
    await user.click(screen.getAllByRole("button", { name: "Ajustar" })[0]);
    const tickets = screen.getByLabelText("Tickets por jogador (k)");
    await user.clear(tickets);
    await user.type(tickets, "1");
    await user.type(screen.getByLabelText("Motivo do override"), "Teste inválido");

    expect(
      screen.getByText("Essa quantidade não cobre o preço no modo padrão. O mínimo para 5x5 é 5."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Salvar tickets" })).toBeDisabled();
    expect(findCall(fetchMock, "PUT", "/api/v1/admin/pricing/band-tickets")).toBeUndefined();
  });

  it("mostra 403 com mensagem própria no catálogo", async () => {
    stubApi({ sportsError: { status: 403, code: "forbidden" } });
    renderPage();

    expect(await screen.findByText("Acesso restrito")).toBeInTheDocument();
    expect(
      screen.getByText("Sua conta não tem permissão de administração da plataforma."),
    ).toBeInTheDocument();
  });

  it("mostra estado vazio sem modalidades", async () => {
    stubApi({ sports: [] });
    renderPage();

    expect(await screen.findByText("Nenhum esporte cadastrado")).toBeInTheDocument();
  });
});
