import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "../../components/ui/Toast";
import { AuthContext } from "../../lib/auth-context";
import type { AdminAuditEvent, AdminUserDetail, AdminUserSummary } from "../../types";
import { AdminUsersPage } from "./AdminUsersPage";

const summary: AdminUserSummary = {
  id: "user-1",
  email: "ana@example.com",
  display_name: "Ana Silva",
  status: "active",
  suspended_until: null,
  created_at: "2026-11-01T12:00:00Z",
};

const detail: AdminUserDetail = {
  ...summary,
  cpf_masked: "***.***.***-**",
  email_verified: false,
};

const auditEvent: AdminAuditEvent = {
  id: "audit-1",
  actor_user_id: "admin-1",
  action: "admin.user.suspend",
  reason: "Abuso confirmado",
  details: null,
  created_at: "2026-11-12T12:00:00Z",
};

interface StubOptions {
  users?: AdminUserSummary[];
  detail?: AdminUserDetail;
  total?: number;
  pageSize?: number;
  audit?: AdminAuditEvent[];
  listError?: { status: number; code: string };
  emailConflict?: boolean;
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

    if (path === "/api/v1/admin/users" && method === "GET") {
      if (options.listError) {
        return jsonResponse({ detail: { code: options.listError.code } }, options.listError.status);
      }
      return jsonResponse({
        users: options.users ?? [summary],
        total: options.total ?? (options.users ?? [summary]).length,
        page: Number(url.searchParams.get("page") ?? "1"),
        page_size: options.pageSize ?? 20,
      });
    }

    if (path === "/api/v1/admin/users" && method === "POST") {
      return jsonResponse(options.detail ?? detail);
    }

    if (path === "/api/v1/admin/users/user-1/audit" && method === "GET") {
      return jsonResponse({ events: options.audit ?? [] });
    }

    if (path === "/api/v1/admin/users/user-1" && method === "GET") {
      return jsonResponse(options.detail ?? detail);
    }

    if (path === "/api/v1/admin/users/user-1/email" && method === "PATCH") {
      if (options.emailConflict) {
        return jsonResponse({ detail: { code: "email_already_registered" } }, 409);
      }
      return jsonResponse(options.detail ?? detail);
    }

    if (path === "/api/v1/admin/users/user-1/password-reset" && method === "POST") {
      return new Response(null, { status: 204 });
    }

    if (path === "/api/v1/admin/users/user-1/suspend" && method === "POST") {
      return jsonResponse({ ...(options.detail ?? detail), status: "suspended" });
    }

    if (path === "/api/v1/admin/users/user-1/reactivate" && method === "POST") {
      return jsonResponse({ ...(options.detail ?? detail), status: "active" });
    }

    if (path === "/api/v1/admin/users/user-1/sessions/revoke" && method === "POST") {
      return jsonResponse({ revoked: 2 });
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
        <MemoryRouter initialEntries={["/admin/users"]}>
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
            <AdminUsersPage />
          </AuthContext.Provider>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

async function openDetail(user: ReturnType<typeof userEvent.setup>) {
  const row = await screen.findByRole("button", { name: /Ana Silva/ });
  await user.click(row);
  await screen.findByText("***.***.***-**");
}

async function fillReason(user: ReturnType<typeof userEvent.setup>, value = "Motivo auditável") {
  await user.type(screen.getByLabelText("Motivo"), value);
}

describe("AdminUsersPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("lista, busca e filtra por status", async () => {
    const fetchMock = stubApi();
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText("Ana Silva")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Buscar"), "ana");
    await user.click(screen.getByRole("button", { name: "Buscar" }));
    await waitFor(() =>
      expect(
        calls(fetchMock).some(
          (call) => call.path === "/api/v1/admin/users" && call.search.get("query") === "ana",
        ),
      ).toBe(true),
    );

    await user.selectOptions(screen.getByLabelText("Status"), "suspended");
    await waitFor(() =>
      expect(
        calls(fetchMock).some(
          (call) =>
            call.path === "/api/v1/admin/users" && call.search.get("status") === "suspended",
        ),
      ).toBe(true),
    );
  });

  it("pagina a lista com o parâmetro page", async () => {
    const fetchMock = stubApi({ total: 45, pageSize: 20 });
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText("Mostrando 1–20 de 45")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Próxima" }));

    await waitFor(() =>
      expect(
        calls(fetchMock).some(
          (call) => call.path === "/api/v1/admin/users" && call.search.get("page") === "2",
        ),
      ).toBe(true),
    );
  });

  it("mostra estado vazio quando não há usuários", async () => {
    stubApi({ users: [] });
    renderPage();

    expect(await screen.findByText("Nenhum usuário encontrado")).toBeInTheDocument();
  });

  it("abre o detalhe com CPF mascarado e auditoria sem paginação", async () => {
    const fetchMock = stubApi({ audit: [auditEvent] });
    const user = userEvent.setup();
    renderPage();

    await openDetail(user);
    expect(await screen.findByText("Usuário suspenso")).toBeInTheDocument();
    expect(screen.getByText("Motivo: Abuso confirmado")).toBeInTheDocument();
    expect(findCall(fetchMock, "GET", "/api/v1/admin/users/user-1")).toBeTruthy();
    expect(screen.getAllByRole("navigation", { name: "Paginação" })).toHaveLength(1);
  });

  it("cria usuário com verify_email=false e sem senha temporária", async () => {
    const fetchMock = stubApi();
    const user = userEvent.setup();
    const logSpy = vi.spyOn(console, "log").mockImplementation(() => undefined);
    renderPage();

    await screen.findByText("Ana Silva");
    await user.click(screen.getByRole("button", { name: "Novo usuário" }));
    await user.type(screen.getByLabelText("E-mail"), "novo@example.com");
    await user.type(screen.getByLabelText("Nome de exibição"), "Novo Operador");
    await user.type(screen.getByLabelText("Senha inicial"), "senha-segura-123");
    await user.type(screen.getByLabelText("Motivo"), "Cadastro operacional");
    await user.click(screen.getByRole("button", { name: "Criar usuário" }));

    expect(await screen.findByText("Usuário criado")).toBeInTheDocument();
    expect(screen.getByText("A conta foi criada com e-mail não verificado.")).toBeInTheDocument();
    const createCall = await waitForCall(fetchMock, "POST", "/api/v1/admin/users");
    expect(createCall.body).toEqual({
      email: "novo@example.com",
      password: "senha-segura-123",
      display_name: "Novo Operador",
      verify_email: false,
      reason: "Cadastro operacional",
    });
    expect(screen.queryByText(/senha temporária/i)).not.toBeInTheDocument();
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
    expect(logSpy.mock.calls.some((args) => String(args[0]).includes("senha-segura-123"))).toBe(
      false,
    );
  });

  it("permite marcar e-mail como verificado como exceção explícita", async () => {
    const fetchMock = stubApi();
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Ana Silva");
    await user.click(screen.getByRole("button", { name: "Novo usuário" }));
    await user.type(screen.getByLabelText("E-mail"), "verificado@example.com");
    await user.type(screen.getByLabelText("Nome de exibição"), "Conta Verificada");
    await user.type(screen.getByLabelText("Senha inicial"), "senha-segura-123");
    await user.type(screen.getByLabelText("Motivo"), "Identidade confirmada");
    await user.click(screen.getByRole("checkbox", { name: /Marcar e-mail como verificado/ }));
    await user.click(screen.getByRole("button", { name: "Criar usuário" }));

    const createCall = await waitForCall(fetchMock, "POST", "/api/v1/admin/users");
    expect(createCall.body?.verify_email).toBe(true);
  });

  it("altera o e-mail com motivo", async () => {
    const fetchMock = stubApi();
    const user = userEvent.setup();
    renderPage();

    await openDetail(user);
    await user.click(screen.getByRole("button", { name: "Alterar e-mail" }));
    await user.clear(screen.getByLabelText("Novo e-mail"));
    await user.type(screen.getByLabelText("Novo e-mail"), "nova@example.com");
    await fillReason(user, "Pedido da usuária");
    await user.click(screen.getByRole("button", { name: "Salvar novo e-mail" }));

    expect(await screen.findByText("E-mail atualizado")).toBeInTheDocument();
    const call = await waitForCall(fetchMock, "PATCH", "/api/v1/admin/users/user-1/email");
    expect(call.body).toEqual({ email: "nova@example.com", reason: "Pedido da usuária" });
  });

  it("mostra o 409 de e-mail duplicado sem fechar a ação", async () => {
    stubApi({ emailConflict: true });
    const user = userEvent.setup();
    renderPage();

    await openDetail(user);
    await user.click(screen.getByRole("button", { name: "Alterar e-mail" }));
    await user.clear(screen.getByLabelText("Novo e-mail"));
    await user.type(screen.getByLabelText("Novo e-mail"), "existente@example.com");
    await fillReason(user, "Pedido da usuária");
    await user.click(screen.getByRole("button", { name: "Salvar novo e-mail" }));

    expect(
      await screen.findByText("Esse e-mail já está vinculado a outra conta. Use outro endereço."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Novo e-mail")).toBeInTheDocument();
  });

  it("envia redefinição e informa que o código foi para o e-mail da conta", async () => {
    const fetchMock = stubApi();
    const user = userEvent.setup();
    renderPage();

    await openDetail(user);
    await user.click(screen.getByRole("button", { name: "Redefinir senha" }));
    await fillReason(user, "Senha esquecida");
    await user.click(screen.getByRole("button", { name: "Enviar código de redefinição" }));

    expect(await screen.findByText("Código enviado para o e-mail da conta")).toBeInTheDocument();
    expect(
      screen.getByText(
        "As sessões foram revogadas e o código de redefinição foi enviado para o e-mail da conta.",
      ),
    ).toBeInTheDocument();
    const call = await waitForCall(fetchMock, "POST", "/api/v1/admin/users/user-1/password-reset");
    expect(call.body).toEqual({ reason: "Senha esquecida" });
    expect(screen.queryByText(/senha temporária/i)).not.toBeInTheDocument();
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
  });

  it("suspende com motivo e prazo opcional", async () => {
    const fetchMock = stubApi();
    const user = userEvent.setup();
    renderPage();

    await openDetail(user);
    await user.click(screen.getByRole("button", { name: "Suspender" }));
    await fillReason(user, "Fraude confirmada");
    fireEvent.change(screen.getByLabelText("Suspender até (opcional)"), {
      target: { value: "2026-12-01T10:00" },
    });
    await user.click(screen.getByRole("button", { name: "Suspender conta" }));

    expect(await screen.findByText("Usuário suspenso")).toBeInTheDocument();
    const call = await waitForCall(fetchMock, "POST", "/api/v1/admin/users/user-1/suspend");
    expect(call.body?.reason).toBe("Fraude confirmada");
    expect(String(call.body?.until)).toMatch(/^2026-12-01T/);
  });

  it("reativa uma conta suspensa com motivo", async () => {
    const suspended: AdminUserDetail = { ...detail, status: "suspended", suspended_until: null };
    const fetchMock = stubApi({ detail: suspended, users: [{ ...summary, status: "suspended" }] });
    const user = userEvent.setup();
    renderPage();

    await openDetail(user);
    await user.click(screen.getByRole("button", { name: "Reativar" }));
    await fillReason(user, "Recurso aceito");
    await user.click(screen.getByRole("button", { name: "Reativar conta" }));

    expect(await screen.findByText("Usuário reativado")).toBeInTheDocument();
    const call = await waitForCall(fetchMock, "POST", "/api/v1/admin/users/user-1/reactivate");
    expect(call.body).toEqual({ reason: "Recurso aceito" });
  });

  it("revoga as sessões com motivo", async () => {
    const fetchMock = stubApi();
    const user = userEvent.setup();
    renderPage();

    await openDetail(user);
    await user.click(screen.getByRole("button", { name: "Revogar sessões" }));
    await fillReason(user, "Dispositivo perdido");
    await user.click(screen.getByRole("button", { name: "Revogar sessões agora" }));

    expect(await screen.findByText("Sessões revogadas")).toBeInTheDocument();
    const call = await waitForCall(fetchMock, "POST", "/api/v1/admin/users/user-1/sessions/revoke");
    expect(call.body).toEqual({ reason: "Dispositivo perdido" });
  });

  it("mostra 403 com mensagem própria", async () => {
    stubApi({ listError: { status: 403, code: "forbidden" } });
    renderPage();

    expect(await screen.findByText("Acesso restrito")).toBeInTheDocument();
    expect(
      screen.getByText("Sua conta não tem permissão de administração da plataforma."),
    ).toBeInTheDocument();
  });
});
