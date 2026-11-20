import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthContext } from "../lib/auth-context";
import { AdminRoute } from "./AdminRoute";

function renderGuard(capabilities: string[], loading = false) {
  render(
    <MemoryRouter initialEntries={["/admin/users"]}>
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
          <Route element={<AdminRoute />}>
            <Route path="/admin/users" element={<p>Conteúdo administrativo</p>} />
          </Route>
        </Routes>
      </AuthContext.Provider>
    </MemoryRouter>,
  );
}

describe("AdminRoute — gate de capability", () => {
  it("redireciona para a raiz sem platform.admin", () => {
    renderGuard(["moderation.read"]);

    expect(screen.getByText("Início")).toBeInTheDocument();
    expect(screen.queryByText("Conteúdo administrativo")).not.toBeInTheDocument();
  });

  it("libera a rota com platform.admin", () => {
    renderGuard(["platform.admin"]);

    expect(screen.getByText("Conteúdo administrativo")).toBeInTheDocument();
    expect(screen.queryByText("Início")).not.toBeInTheDocument();
  });

  it("mostra carregamento enquanto a sessão é verificada", () => {
    renderGuard([], true);

    expect(screen.getByText("Verificando permissão de administração...")).toBeInTheDocument();
    expect(screen.queryByText("Conteúdo administrativo")).not.toBeInTheDocument();
  });
});
