import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { NotificationCenter } from "./NotificationCenter";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname + location.search + location.hash}</div>;
}

function renderCenter() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/"]}>
        <NotificationCenter />
        <Routes>
          <Route path="*" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return client;
}

const appealNotification = {
  id: "notification-1",
  kind: "moderation_appeal",
  title: "Novo recurso",
  body: "Uma medida foi contestada. Revise o recurso na fila interna.",
  data: { appeal_id: "appeal-1" },
  created_at: new Date(Date.now() - 60_000).toISOString(),
  read_at: null,
};

const reportNotification = {
  id: "notification-2",
  kind: "moderation_report",
  title: "Nova denúncia",
  body: "ABUSE · HIGH · prioridade 72",
  data: { report_id: "report-1" },
  created_at: new Date(Date.now() - 3 * 60_000).toISOString(),
  read_at: new Date().toISOString(),
};

function stubApi(notifications: unknown[] = [appealNotification, reportNotification]) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (url.includes("/moderation/notifications/unread-count")) {
      return jsonResponse({ unread_count: 1 });
    }
    if (url.includes("/read-all") && method === "POST") {
      return jsonResponse({ marked: 1, unread_count: 0 });
    }
    if (url.includes("/read") && method === "POST") {
      return jsonResponse({ ...appealNotification, read_at: new Date().toISOString() });
    }
    if (url.includes("/moderation/notifications?")) {
      return jsonResponse({
        notifications,
        unread_count: notifications.filter((item) => !(item as { read_at: unknown }).read_at)
          .length,
        limit: 30,
        offset: 0,
      });
    }
    return jsonResponse({ detail: { code: "not_found" } }, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("NotificationCenter", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("mostra o sino com a contagem de não lidas", async () => {
    stubApi();
    renderCenter();

    const bell = await screen.findByRole("button", { name: "Notificações, 1 não lidas" });
    expect(bell).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("abre o painel lateral e lista as notificações", async () => {
    stubApi();
    const user = userEvent.setup();
    renderCenter();

    await user.click(await screen.findByRole("button", { name: /Notificações/ }));

    expect(await screen.findByRole("dialog", { name: "Notificações" })).toBeInTheDocument();
    expect(await screen.findByText("Novo recurso")).toBeInTheDocument();
    expect(screen.getByText("Nova denúncia")).toBeInTheDocument();
    expect(screen.getAllByText("Recurso").length).toBeGreaterThan(0);
  });

  it("marca como lida e navega para a fila de recursos ao abrir um recurso", async () => {
    const fetchMock = stubApi();
    const user = userEvent.setup();
    renderCenter();

    await user.click(await screen.findByRole("button", { name: /Notificações/ }));
    await user.click(await screen.findByRole("button", { name: /Novo recurso/ }));

    await waitFor(() =>
      expect(screen.getByTestId("location")).toHaveTextContent(
        "/moderation?appeal=appeal-1#appeals",
      ),
    );
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url).includes("/moderation/notifications/notification-1/read") &&
          (init as RequestInit | undefined)?.method === "POST",
      ),
    ).toBe(true);
  });

  it("navega para o relatório usando report_id", async () => {
    stubApi();
    const user = userEvent.setup();
    renderCenter();

    await user.click(await screen.findByRole("button", { name: /Notificações/ }));
    await user.click(await screen.findByRole("button", { name: /Nova denúncia/ }));

    await waitFor(() =>
      expect(screen.getByTestId("location")).toHaveTextContent("/moderation?report=report-1"),
    );
  });

  it("marca todas como lidas", async () => {
    const fetchMock = stubApi();
    const user = userEvent.setup();
    renderCenter();

    await user.click(await screen.findByRole("button", { name: /Notificações/ }));
    await user.click(await screen.findByRole("button", { name: "Marcar todas como lidas" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) =>
          String(url).includes("/moderation/notifications/read-all"),
        ),
      ).toBe(true),
    );
  });

  it("mostra estado vazio quando não há notificações", async () => {
    stubApi([]);
    const user = userEvent.setup();
    renderCenter();

    await user.click(await screen.findByRole("button", { name: /Notificações/ }));
    expect(await screen.findByText("Nenhuma notificação")).toBeInTheDocument();
  });
});
