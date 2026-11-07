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
});
