import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthContext } from "../lib/auth-context";
import type { ModerationReport } from "../types";
import { ModerationPage } from "./ModerationPage";

const report: ModerationReport = {
  id: "report-1",
  category: "HARASSMENT",
  status: "OPEN",
  severity: "HIGH",
  priority: 90,
  created_at: "2026-11-14T12:00:00Z",
  reviewed_at: null,
  decision_reason: null,
  reporter_id: "user-reporter",
  target_user_id: "user-target",
  lobby_id: "lobby-1",
  description: "Ofensas repetidas no chat",
  context: [
    {
      id: "message-1",
      sender_id: "user-target",
      body: "Mensagem ofensiva",
      created_at: "2026-11-14T11:59:00Z",
    },
  ],
  classifier_version: "rules_v1",
  classifier_signals: null,
  reviewed_by: null,
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubApi(role: "ADMIN" | "MODERATOR" | null) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith("/api/v1/moderation/me")) {
      return role
        ? jsonResponse({ user_id: "user-admin", role })
        : jsonResponse({ detail: { code: "moderator_required" } }, 403);
    }
    if (url.includes("/moderation/queue")) {
      return jsonResponse({
        reports: [report],
        stats: { open: 1, in_review: 0, appealed: 0, high_priority: 1 },
      });
    }
    if (url.includes("/moderation/reports/report-1/decision")) {
      expect(init?.method).toBe("POST");
      return jsonResponse({ ...report, status: "RESOLVED" });
    }
    if (url.includes("/moderation/appeals")) return jsonResponse([]);
    if (url.includes("/moderation/operators")) {
      return jsonResponse([
        {
          user_id: "user-admin",
          role: "ADMIN",
          active: true,
          created_at: "2026-11-14T12:00:00Z",
          deactivated_at: null,
        },
      ]);
    }
    return jsonResponse({ detail: { code: "not_found" } }, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/moderation"]}>
        <AuthContext.Provider
          value={{
            user: { id: "user-admin", status: "active" },
            loading: false,
            signIn: vi.fn(),
            signOut: vi.fn(),
          }}
        >
          <ModerationPage />
        </AuthContext.Provider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ModerationPage — fila interna", () => {
  it("bloqueia quem não é moderador", async () => {
    stubApi(null);
    renderPage();

    expect(await screen.findByText("Acesso restrito")).toBeInTheDocument();
    expect(screen.getByText(/Sua conta não tem permissão de moderação/)).toBeInTheDocument();
  });

  it("admin vê fila, contexto e registra decisão", async () => {
    stubApi("ADMIN");
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText("Ofensas repetidas no chat")).toBeInTheDocument();
    expect(screen.getByText("Mensagem ofensiva")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Moderadores" })).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Medida"), "WARN");
    await user.type(screen.getByLabelText("Justificativa"), "Aviso formal");
    await user.click(screen.getByRole("button", { name: "Registrar decisão" }));

    expect(await screen.findByText("Denúncia decidida: Resolvida.")).toBeInTheDocument();
  });
});
