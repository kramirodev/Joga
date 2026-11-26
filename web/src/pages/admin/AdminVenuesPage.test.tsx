import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "../../components/ui/Toast";
import { AuthContext } from "../../lib/auth-context";
import type { AdminVenue } from "../../types";
import { AdminVenuesPage } from "./AdminVenuesPage";

const platformVenue: AdminVenue = {
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
  spaces_count: 2,
  active_spaces_count: 1,
  created_at: "2026-11-01T12:00:00Z",
  updated_at: "2026-11-02T12:00:00Z",
};

const partnerVenue: AdminVenue = {
  id: "venue-2",
  organization_id: "org-partner",
  organization_name: "Arena Tijuca",
  organization_is_platform: false,
  organization_status: "active",
  name: "Quadra do Parceiro",
  city: "Niterói",
  state: "RJ",
  address_line: "Rua do Parceiro, 25",
  postal_code: "24000000",
  latitude: -22.88,
  longitude: -43.1,
  is_public: false,
  status: "inactive",
  spaces_count: 3,
  active_spaces_count: 0,
  created_at: "2026-10-20T12:00:00Z",
  updated_at: "2026-10-21T12:00:00Z",
};

interface StubOptions {
  venues?: AdminVenue[];
  total?: number;
  pageSize?: number;
  listError?: { status: number; code: string };
  actionError?: { status: number; code: string };
  patchError?: { status: number; code: string };
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
  const venues = options.venues ?? [platformVenue, partnerVenue];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://joga.local");
    const method = (init?.method ?? "GET").toUpperCase();
    const path = url.pathname;

    if (path === "/api/v1/admin/venues" && method === "GET") {
      if (options.listError) {
        return jsonResponse({ detail: { code: options.listError.code } }, options.listError.status);
      }
      return jsonResponse({
        total: options.total ?? venues.length,
        page: Number(url.searchParams.get("page") ?? "1"),
        page_size: options.pageSize ?? 20,
        venues,
      });
    }

    if (path === "/api/v1/admin/venues" && method === "POST") {
      return jsonResponse({ ...platformVenue, id: "venue-new", name: "Arena Nova" }, 201);
    }

    if (path === "/api/v1/admin/venues/venue-1/suspend" && method === "POST") {
      if (options.actionError) {
        return jsonResponse(
          { detail: { code: options.actionError.code } },
          options.actionError.status,
        );
      }
      return jsonResponse({ ...platformVenue, status: "inactive" });
    }

    if (path === "/api/v1/admin/venues/venue-1/reactivate" && method === "POST") {
      if (options.actionError) {
        return jsonResponse(
          { detail: { code: options.actionError.code } },
          options.actionError.status,
        );
      }
      return jsonResponse({ ...platformVenue, status: "active" });
    }

    if (path === "/api/v1/admin/venues/venue-1" && method === "PATCH") {
      if (options.patchError) {
        return jsonResponse(
          { detail: { code: options.patchError.code } },
          options.patchError.status,
        );
      }
      return jsonResponse(platformVenue);
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
            <AdminVenuesPage />
          </AuthContext.Provider>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

async function openSuspend(name = "Arena Pública") {
  renderPage();
  await screen.findByText(name);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: `Suspender ${name}` }));
  return user;
}

describe("AdminVenuesPage", () => {
  it("lista quadras de todas as organizações com as colunas de moderação", async () => {
    stubApi();
    renderPage();

    expect(await screen.findByText("Arena Pública")).toBeInTheDocument();
    expect(screen.getByText("Quadra do Parceiro")).toBeInTheDocument();
    expect(screen.getByText("JOGA Público")).toBeInTheDocument();
    expect(screen.getByText("Arena Tijuca")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Quadra" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Organização" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Status" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Pública" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Espaços" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Criada em" })).toBeInTheDocument();
    expect(screen.getByText("1 de 2 espaços ativos")).toBeInTheDocument();
    expect(screen.getByText("0 de 3 espaços ativos")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Suspender Arena Pública" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reativar Quadra do Parceiro" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Editar Arena Pública" })).toBeInTheDocument();
  });

  it("não oferece ação de exclusão em nenhuma linha", async () => {
    stubApi();
    renderPage();
    await screen.findByText("Arena Pública");

    expect(
      screen.queryByRole("button", { name: /excluir|remover|apagar/i }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/excluir/i)).not.toBeInTheDocument();
  });

  it("busca e filtra por status e visibilidade", async () => {
    const fetchMock = stubApi();
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Arena Pública");
    await user.type(screen.getByLabelText("Buscar"), "tijuca");
    await user.click(screen.getByRole("button", { name: "Buscar" }));
    await user.selectOptions(screen.getByLabelText("Status"), "inactive");
    await user.selectOptions(screen.getByLabelText("Visibilidade"), "false");

    await waitFor(() => {
      const filtered = calls(fetchMock).find(
        (call) =>
          call.method === "GET" &&
          call.path === "/api/v1/admin/venues" &&
          call.search.get("q") === "tijuca" &&
          call.search.get("status") === "inactive" &&
          call.search.get("is_public") === "false",
      );
      expect(filtered).toBeTruthy();
    });
    const filtered = calls(fetchMock).find(
      (call) =>
        call.method === "GET" &&
        call.path === "/api/v1/admin/venues" &&
        call.search.get("q") === "tijuca" &&
        call.search.get("status") === "inactive" &&
        call.search.get("is_public") === "false",
    );
    expect(filtered?.search.get("page")).toBe("1");
    expect(filtered?.search.get("page_size")).toBe("20");
  });

  it("mostra total e navega entre páginas", async () => {
    const fetchMock = stubApi({ total: 45, pageSize: 20, venues: [platformVenue] });
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText("Mostrando 1–20 de 45")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Próxima" }));

    await waitFor(() =>
      expect(
        calls(fetchMock).some(
          (call) =>
            call.method === "GET" &&
            call.path === "/api/v1/admin/venues" &&
            call.search.get("page") === "2",
        ),
      ).toBe(true),
    );
  });

  it("suspende a quadra com motivo e atualiza a lista", async () => {
    const fetchMock = stubApi();
    const user = await openSuspend();

    expect(screen.getByRole("dialog", { name: "Suspender quadra" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Motivo"), "Cadastro com informações incorretas");
    await user.click(screen.getByRole("button", { name: "Suspender quadra" }));

    expect(await screen.findByText("Quadra suspensa")).toBeInTheDocument();
    const call = await waitForCall(fetchMock, "POST", "/api/v1/admin/venues/venue-1/suspend");
    expect(call.body).toEqual({ reason: "Cadastro com informações incorretas" });
    await waitFor(() =>
      expect(
        calls(fetchMock).filter(
          (item) => item.method === "GET" && item.path === "/api/v1/admin/venues",
        ).length,
      ).toBeGreaterThan(1),
    );
  });

  it("bloqueia a confirmação enquanto o motivo estiver vazio ou curto", async () => {
    stubApi();
    const user = await openSuspend();

    const confirm = screen.getByRole("button", { name: "Suspender quadra" });
    expect(confirm).toBeDisabled();

    await user.type(screen.getByLabelText("Motivo"), "  ");
    expect(confirm).toBeDisabled();

    await user.clear(screen.getByLabelText("Motivo"));
    await user.type(screen.getByLabelText("Motivo"), "ab");
    expect(confirm).toBeDisabled();

    await user.type(screen.getByLabelText("Motivo"), "c");
    expect(confirm).toBeEnabled();
  });

  it("reativa a quadra com motivo", async () => {
    const fetchMock = stubApi({ venues: [{ ...platformVenue, status: "inactive" }] });
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Arena Pública");
    await user.click(screen.getByRole("button", { name: "Reativar Arena Pública" }));
    expect(screen.getByRole("dialog", { name: "Reativar quadra" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Motivo"), "Correção concluída");
    await user.click(screen.getByRole("button", { name: "Reativar quadra" }));

    expect(await screen.findByText("Quadra reativada")).toBeInTheDocument();
    const call = await waitForCall(fetchMock, "POST", "/api/v1/admin/venues/venue-1/reactivate");
    expect(call.body).toEqual({ reason: "Correção concluída" });
  });

  it("edita somente campos cadastrais com motivo", async () => {
    const fetchMock = stubApi({ venues: [platformVenue] });
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Arena Pública");
    await user.click(screen.getByRole("button", { name: "Editar Arena Pública" }));
    expect(screen.getByRole("dialog", { name: "Editar Arena Pública" })).toBeInTheDocument();
    expect(screen.getByLabelText("Nome da quadra")).toHaveValue("Arena Pública");

    await user.clear(screen.getByLabelText("Nome da quadra"));
    await user.type(screen.getByLabelText("Nome da quadra"), "Arena Pública Revisada");
    await user.clear(screen.getByLabelText("Cidade"));
    await user.type(screen.getByLabelText("Cidade"), "São Gonçalo");
    await user.click(screen.getByLabelText("Aparece na descoberta do aplicativo"));
    await user.type(screen.getByLabelText("Motivo"), "Correção de cadastro");
    await user.click(screen.getByRole("button", { name: "Salvar alterações" }));

    expect(await screen.findByText("Quadra atualizada")).toBeInTheDocument();
    const call = await waitForCall(fetchMock, "PATCH", "/api/v1/admin/venues/venue-1");
    expect(call.body).toMatchObject({
      name: "Arena Pública Revisada",
      city: "São Gonçalo",
      state: "RJ",
      address_line: "Rua das Quadras, 10",
      postal_code: "20000000",
      latitude: -22.9068,
      longitude: -43.1729,
      is_public: false,
      reason: "Correção de cadastro",
    });
  });

  it("mostra estado vazio", async () => {
    stubApi({ venues: [] });
    renderPage();

    expect(await screen.findByText("Nenhuma quadra encontrada")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Quando uma organização cadastrar uma quadra, ela aparece aqui para moderação.",
      ),
    ).toBeInTheDocument();
  });

  it("mostra 403 com mensagem própria", async () => {
    stubApi({ listError: { status: 403, code: "forbidden" } });
    renderPage();

    expect(await screen.findByText("Acesso restrito")).toBeInTheDocument();
    expect(
      screen.getByText("Sua conta não tem permissão de administração da plataforma."),
    ).toBeInTheDocument();
  });

  it("traduz 404 ao suspender e mantém o diálogo aberto", async () => {
    stubApi({ actionError: { status: 404, code: "venue_not_found" } });
    const user = await openSuspend();

    await user.type(screen.getByLabelText("Motivo"), "Cadastro incorreto");
    await user.click(screen.getByRole("button", { name: "Suspender quadra" }));

    expect(
      await screen.findByText("Quadra não encontrada. Atualize a lista e tente novamente."),
    ).toBeInTheDocument();
    expect(screen.getByRole("dialog", { name: "Suspender quadra" })).toBeInTheDocument();
  });

  it("traduz 404 ao editar", async () => {
    stubApi({ patchError: { status: 404, code: "venue_not_found" } });
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Arena Pública");
    await user.click(screen.getByRole("button", { name: "Editar Arena Pública" }));
    const dialog = screen.getByRole("dialog", { name: "Editar Arena Pública" });
    await user.type(within(dialog).getByLabelText("Motivo"), "Correção de cadastro");
    await user.click(screen.getByRole("button", { name: "Salvar alterações" }));

    expect(
      await screen.findByText("Quadra não encontrada. Atualize a lista e tente novamente."),
    ).toBeInTheDocument();
  });

  it("abre o gerenciamento de espaços e agenda a partir da lista", async () => {
    stubApi();
    renderPage();

    await screen.findByText("Arena Pública");
    expect(
      screen.getByRole("link", {
        name: "Gerenciar espaços e agenda de Arena Pública",
      }),
    ).toHaveAttribute("href", "/admin/venues/venue-1");
  });

  it("cria uma quadra da plataforma pela ação Nova quadra", async () => {
    const fetchMock = stubApi();
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Arena Pública");
    await user.click(screen.getByRole("button", { name: "Nova quadra" }));

    const dialog = screen.getByRole("dialog", { name: "Nova quadra" });
    await user.type(within(dialog).getByLabelText("Nome da quadra"), "Arena Nova");
    await user.type(within(dialog).getByLabelText("Cidade"), "Rio de Janeiro");
    await user.type(within(dialog).getByLabelText("UF"), "RJ");
    await user.type(within(dialog).getByLabelText("Endereço"), "Rua Nova, 100");
    await user.click(
      within(dialog).getByRole("button", { name: "Ajustar coordenadas manualmente" }),
    );
    await user.type(within(dialog).getByLabelText("Latitude"), "-22.9");
    await user.type(within(dialog).getByLabelText("Longitude"), "-43.2");
    await user.type(within(dialog).getByLabelText("Motivo"), "Cadastro inicial da quadra");
    await user.click(within(dialog).getByRole("button", { name: "Criar quadra" }));

    const call = await waitForCall(fetchMock, "POST", "/api/v1/admin/venues");
    expect(call.body).toMatchObject({
      name: "Arena Nova",
      city: "Rio de Janeiro",
      state: "RJ",
      address_line: "Rua Nova, 100",
      latitude: -22.9,
      longitude: -43.2,
      is_public: true,
      reason: "Cadastro inicial da quadra",
    });
    expect(await screen.findByText("Quadra criada")).toBeInTheDocument();
  });
});
