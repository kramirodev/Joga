import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthContext } from "../lib/auth-context";
import { ModerationRoute } from "./ModerationRoute";

function renderGuard(capabilities: string[], loading = false) {
  render(
    <MemoryRouter initialEntries={["/moderation"]}>
      <AuthContext.Provider
        value={{
          user: { id: "user-1", status: "active" },
          capabilities,
          loading,
          sessionExpired: false,
          signIn: vi.fn(),
          signOut: vi.fn(),
        }}
      >
        <Routes>
          <Route path="/" element={<p>Início</p>} />
          <Route element={<ModerationRoute />}>
            <Route path="/moderation" element={<p>Conteúdo de moderação</p>} />
          </Route>
        </Routes>
      </AuthContext.Provider>
    </MemoryRouter>,
  );
}

describe("ModerationRoute — gate de capability", () => {
  it("redireciona jogador para a raiz sem moderation.read", () => {
    renderGuard([]);

    expect(screen.getByText("Início")).toBeInTheDocument();
    expect(screen.queryByText("Conteúdo de moderação")).not.toBeInTheDocument();
  });

  it("libera a rota para moderador com moderation.read", () => {
    renderGuard(["moderation.read"]);

    expect(screen.getByText("Conteúdo de moderação")).toBeInTheDocument();
    expect(screen.queryByText("Início")).not.toBeInTheDocument();
  });

  it("libera a rota para administrador da plataforma", () => {
    renderGuard(["platform.admin", "moderation.read", "moderation.manage"]);

    expect(screen.getByText("Conteúdo de moderação")).toBeInTheDocument();
    expect(screen.queryByText("Início")).not.toBeInTheDocument();
  });

  it("mostra carregamento enquanto a sessão é verificada", () => {
    renderGuard([], true);

    expect(screen.getByText("Verificando permissão de moderação...")).toBeInTheDocument();
    expect(screen.queryByText("Conteúdo de moderação")).not.toBeInTheDocument();
  });
});
