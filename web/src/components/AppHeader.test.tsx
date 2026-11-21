import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthContext } from "../lib/auth-context";
import { AppHeader } from "./AppHeader";

function renderHeader(capabilities: string[]) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(JSON.stringify({ unread_count: 0 }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    ),
  );
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/"]}>
        <AuthContext.Provider
          value={{
            user: { id: "user-1", status: "active" },
            capabilities,
            loading: false,
            sessionExpired: false,
            signIn: vi.fn(),
            signOut: vi.fn(),
          }}
        >
          <AppHeader />
        </AuthContext.Provider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("AppHeader — moderação por capability", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("não mostra moderação nem sino sem moderation.read", () => {
    renderHeader([]);
    expect(screen.queryByRole("link", { name: "Moderação" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Notificações/ })).not.toBeInTheDocument();
  });

  it("mostra moderação e sino com moderation.read", () => {
    renderHeader(["moderation.read"]);
    expect(screen.getByRole("link", { name: "Moderação" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Notificações" })).toBeInTheDocument();
  });

  it("mostra moderação para platform.admin mesmo sem moderation.read", () => {
    renderHeader(["platform.admin"]);
    expect(screen.getByRole("link", { name: "Moderação" })).toBeInTheDocument();
    // O sino continua dependendo de moderation.read; o link é só descoberta.
    expect(screen.queryByRole("button", { name: /Notificações/ })).not.toBeInTheDocument();
  });

  it("não duplica o link de moderação quando as duas capabilities existem", () => {
    renderHeader(["platform.admin", "moderation.read"]);
    expect(screen.getAllByRole("link", { name: "Moderação" })).toHaveLength(1);
  });

  it("esconde a administração sem platform.admin", () => {
    renderHeader(["moderation.read"]);
    expect(screen.queryByRole("link", { name: "Usuários" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Esportes" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Quadras" })).not.toBeInTheDocument();
  });

  it("mostra a administração com platform.admin", () => {
    renderHeader(["platform.admin"]);
    expect(screen.getByRole("link", { name: "Usuários" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Esportes" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Quadras" })).toBeInTheDocument();
  });

  it("troca a senha autenticada com senha atual e nova", async () => {
    const user = userEvent.setup();
    renderHeader([]);
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await user.click(screen.getByRole("button", { name: "Alterar senha" }));
    await user.type(screen.getByLabelText("Senha atual"), "senha-atual-123");
    await user.type(screen.getByLabelText("Nova senha"), "nova-senha-123");
    await user.type(screen.getByLabelText("Confirmar nova senha"), "nova-senha-123");
    await user.click(screen.getByRole("button", { name: "Salvar nova senha" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(new URL(url, "http://joga.local").pathname).toBe("/api/v1/me/password");
    expect(JSON.parse(String(init.body))).toEqual({
      current_password: "senha-atual-123",
      new_password: "nova-senha-123",
    });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("não envia a troca quando a confirmação diverge", async () => {
    const user = userEvent.setup();
    renderHeader([]);
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await user.click(screen.getByRole("button", { name: "Alterar senha" }));
    await user.type(screen.getByLabelText("Senha atual"), "senha-atual-123");
    await user.type(screen.getByLabelText("Nova senha"), "nova-senha-123");
    await user.type(screen.getByLabelText("Confirmar nova senha"), "nova-senha-124");
    await user.click(screen.getByRole("button", { name: "Salvar nova senha" }));

    expect(await screen.findByText("As senhas não coincidem.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("aponta a senha atual incorreta sem repetir o erro genérico de login", async () => {
    const user = userEvent.setup();
    renderHeader([]);
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: { code: "invalid_credentials" } }), {
            status: 401,
            headers: { "Content-Type": "application/json" },
          }),
      ),
    );

    await user.click(screen.getByRole("button", { name: "Alterar senha" }));
    await user.type(screen.getByLabelText("Senha atual"), "senha-errada-123");
    await user.type(screen.getByLabelText("Nova senha"), "nova-senha-123");
    await user.type(screen.getByLabelText("Confirmar nova senha"), "nova-senha-123");
    await user.click(screen.getByRole("button", { name: "Salvar nova senha" }));

    expect(await screen.findByText("A senha atual está incorreta.")).toBeInTheDocument();
    expect(screen.queryByText("E-mail ou senha inválidos.")).not.toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});
