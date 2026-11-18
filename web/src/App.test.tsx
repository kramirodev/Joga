import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import App from "./App";
import { clearAuthTokens } from "./lib/api";

describe("rotas do painel", () => {
  beforeEach(() => {
    clearAuthTokens();
    window.history.pushState({}, "", "/");
  });

  it("redireciona visitante sem sessão para o login", async () => {
    render(<App />);

    expect(await screen.findByRole("tab", { name: "Entrar" })).toBeInTheDocument();
    expect(window.location.pathname).toBe("/login");
  });

  it("preserva o destino ao redirecionar por sessão ausente", async () => {
    window.history.pushState({}, "", "/organizations/org-1?tab=bookings#top");
    render(<App />);

    expect(await screen.findByRole("tab", { name: "Entrar" })).toBeInTheDocument();
    expect(window.location.pathname).toBe("/login");
    const state = window.history.state as { usr?: { from?: string } } | null;
    expect(state?.usr?.from).toBe("/organizations/org-1?tab=bookings#top");
  });
});
