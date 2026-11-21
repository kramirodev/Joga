import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "../components/ui/Toast";
import type { Organization } from "../types";
import { OrganizationsPage } from "./OrganizationsPage";

const createdOrganization: Organization = {
  id: "org-1",
  name: "Arena Tijuca",
  status: "active",
  role: "OWNER",
  cnpj: "11222333000181",
  cnpj_status: "ATIVA",
  verification_status: "verified",
  cnpj_verified_at: "2026-11-21T12:00:00Z",
  cnpj_next_check_at: "2026-11-28T12:00:00Z",
  payout_ready: false,
  payout_status: "pending",
  pix_key_type: null,
  pix_key_masked: null,
  created_at: "2026-11-21T12:00:00Z",
  updated_at: "2026-11-21T12:00:00Z",
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubApi(createResponse: Response = jsonResponse(createdOrganization, 201)) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(String(input), "http://joga.local").pathname;
    if (path === "/api/v1/organizations" && init?.method === "GET") {
      return jsonResponse({ organizations: [] });
    }
    if (path === "/api/v1/organizations" && init?.method === "POST") {
      return createResponse;
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
        <MemoryRouter initialEntries={["/"]}>
          <Routes>
            <Route path="/" element={<OrganizationsPage />} />
            <Route path="/organizations/:organizationId" element={<div>destino</div>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function postBodies(fetchMock: ReturnType<typeof vi.fn>) {
  return fetchMock.mock.calls
    .filter(([, init]) => (init as RequestInit | undefined)?.method === "POST")
    .map(([, init]) => JSON.parse(String((init as RequestInit).body)) as Record<string, unknown>);
}

describe("OrganizationsPage — criação com CNPJ", () => {
  it("envia nome, CNPJ e CPF normalizados e não reexibe o CPF", async () => {
    const fetchMock = stubApi();
    const user = userEvent.setup();
    renderPage();

    await screen.findByRole("heading", { name: "Nova organização" });
    await user.type(screen.getByLabelText("Nome da organização ou arena"), "Arena Tijuca");
    await user.type(screen.getByLabelText("CNPJ"), "11222333000181");
    await user.type(screen.getByLabelText("CPF do responsável"), "11144477735");
    expect(screen.getByLabelText("CPF do responsável")).toHaveValue("111.444.777-35");

    await user.click(screen.getByRole("button", { name: "Verificar CNPJ e criar" }));

    expect(await screen.findByText("destino")).toBeInTheDocument();
    expect(postBodies(fetchMock)).toEqual([
      {
        name: "Arena Tijuca",
        cnpj: "11222333000181",
        cpf: "11144477735",
      },
    ]);
  });

  it("valida CNPJ e CPF antes de chamar o servidor", async () => {
    const fetchMock = stubApi();
    const user = userEvent.setup();
    renderPage();

    await user.type(await screen.findByLabelText("Nome da organização ou arena"), "Arena Tijuca");
    await user.type(screen.getByLabelText("CNPJ"), "11222333000180");
    await user.type(screen.getByLabelText("CPF do responsável"), "11111111111");
    await user.click(screen.getByRole("button", { name: "Verificar CNPJ e criar" }));

    expect(await screen.findByText("CNPJ inválido. Confira os dígitos.")).toBeInTheDocument();
    expect(screen.getByText("CPF inválido. Confira os dígitos.")).toBeInTheDocument();
    expect(postBodies(fetchMock)).toHaveLength(0);
  });

  it("mostra o motivo estável quando o CNPJ não está ativo", async () => {
    const fetchMock = stubApi(jsonResponse({ detail: { code: "cnpj_inactive" } }, 422));
    const user = userEvent.setup();
    renderPage();

    await user.type(await screen.findByLabelText("Nome da organização ou arena"), "Arena Tijuca");
    await user.type(screen.getByLabelText("CNPJ"), "11222333000181");
    await user.type(screen.getByLabelText("CPF do responsável"), "11144477735");
    await user.click(screen.getByRole("button", { name: "Verificar CNPJ e criar" }));

    expect(
      await screen.findByText(
        "Esse CNPJ não está ativo na Receita Federal. Regularize a situação da empresa antes de continuar.",
      ),
    ).toBeInTheDocument();
    await waitFor(() => expect(postBodies(fetchMock)).toHaveLength(1));
  });
});
