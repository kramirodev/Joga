import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
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
});
