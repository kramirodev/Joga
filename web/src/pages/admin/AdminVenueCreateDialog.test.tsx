import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { PostalCodeLookup } from "../../types";
import { AdminVenueCreateDialog } from "./AdminVenueCreateDialog";

function lookupResponse(overrides: Partial<PostalCodeLookup> = {}): PostalCodeLookup {
  return {
    postal_code: "20541004",
    street: "Rua das Laranjeiras",
    neighborhood: "Laranjeiras",
    city: "Rio de Janeiro",
    state: "RJ",
    country: "BR",
    latitude: -22.934,
    longitude: -43.201,
    precision: "street",
    source: "brasilapi",
    resolved_at: "2026-11-01T12:00:00Z",
    ...overrides,
  };
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubApi(
  lookup: (cep: string) => Response | Promise<Response> = () => jsonResponse(lookupResponse()),
) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://joga.local");
    const path = url.pathname;
    if (path.startsWith("/api/v1/geo/postal-codes/")) {
      return lookup(path.split("/").pop() ?? "");
    }
    if (path === "/api/v1/admin/venues" && init?.method === "POST") {
      return jsonResponse({ id: "venue-new" }, 201);
    }
    return jsonResponse({ detail: { code: "not_found" } }, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderDialog() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const onCreated = vi.fn();
  render(
    <QueryClientProvider client={queryClient}>
      <AdminVenueCreateDialog open onClose={() => {}} onCreated={onCreated} />
    </QueryClientProvider>,
  );
  return onCreated;
}

function geoCalls(fetchMock: ReturnType<typeof stubApi>) {
  return fetchMock.mock.calls.filter(([url]) => String(url).includes("/geo/postal-codes/"));
}

function createCalls(fetchMock: ReturnType<typeof stubApi>) {
  return fetchMock.mock.calls.filter(
    ([url, init]) =>
      String(url).endsWith("/admin/venues") && (init as RequestInit | undefined)?.method === "POST",
  );
}

function dialog() {
  return within(screen.getByRole("dialog", { name: "Nova quadra" }));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AdminVenueCreateDialog — cadastro com CEP", () => {
  it("consulta o CEP automaticamente e preenche cidade, UF, endereço e coordenadas", async () => {
    const fetchMock = stubApi();
    const user = userEvent.setup();
    renderDialog();

    const form = dialog();
    await user.type(form.getByLabelText("Nome da quadra"), "Arena Nova");
    await user.type(form.getByLabelText("CEP"), "20541004");

    await waitFor(() => expect(form.getByLabelText("Cidade")).toHaveValue("Rio de Janeiro"), {
      timeout: 2500,
    });
    expect(form.getByLabelText("UF")).toHaveValue("RJ");
    expect(form.getByLabelText("Endereço")).toHaveValue("Rua das Laranjeiras");
    expect(form.getByText(/Coordenadas: -22\.934, -43\.201/)).toBeInTheDocument();
    expect(form.getByRole("button", { name: "Ajustar coordenadas manualmente" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(form.queryByLabelText("Latitude")).not.toBeInTheDocument();

    await user.type(form.getByLabelText("Motivo"), "Cadastro inicial da quadra");
    await user.click(form.getByRole("button", { name: "Criar quadra" }));

    await waitFor(() => expect(createCalls(fetchMock)).toHaveLength(1));
    const body = JSON.parse(String((createCalls(fetchMock)[0][1] as RequestInit).body));
    expect(body).toMatchObject({
      name: "Arena Nova",
      city: "Rio de Janeiro",
      state: "RJ",
      address_line: "Rua das Laranjeiras",
      postal_code: "20541004",
      latitude: -22.934,
      longitude: -43.201,
      is_public: true,
    });
    expect(body).not.toHaveProperty("geocoding_source");
    expect(body).not.toHaveProperty("geocoding_precision");
  });

  it("abre o ajuste manual quando o CEP não traz coordenadas e exige o ponto", async () => {
    const fetchMock = stubApi(() =>
      jsonResponse(lookupResponse({ latitude: null, longitude: null, precision: "unresolved" })),
    );
    const user = userEvent.setup();
    renderDialog();

    const form = dialog();
    await user.type(form.getByLabelText("Nome da quadra"), "Arena Nova");
    await user.type(form.getByLabelText("CEP"), "20541004");
    await user.type(form.getByLabelText("Motivo"), "Cadastro inicial da quadra");

    expect(
      await form.findByText(/Não foi possível obter as coordenadas deste CEP/, undefined, {
        timeout: 2500,
      }),
    ).toBeInTheDocument();
    expect(form.getByRole("button", { name: "Ocultar ajuste manual" })).toBeInTheDocument();
    expect(form.getByLabelText("Latitude")).toHaveValue("");

    await user.click(form.getByRole("button", { name: "Criar quadra" }));
    expect(await form.findByText("Informe a latitude.")).toBeInTheDocument();
    expect(createCalls(fetchMock)).toHaveLength(0);

    await user.type(form.getByLabelText("Latitude"), "-22.95");
    await user.type(form.getByLabelText("Longitude"), "-43.21");
    await user.click(form.getByRole("button", { name: "Criar quadra" }));

    await waitFor(() => expect(createCalls(fetchMock)).toHaveLength(1));
    const body = JSON.parse(String((createCalls(fetchMock)[0][1] as RequestInit).body));
    expect(body.latitude).toBe(-22.95);
    expect(body.longitude).toBe(-43.21);
  });

  it("preserva coordenadas digitadas manualmente quando o CEP volta sem coordenadas", async () => {
    let resolveLookup: (response: Response) => void = () => {};
    const pending = new Promise<Response>((resolve) => {
      resolveLookup = resolve;
    });
    const fetchMock = stubApi(() => pending);
    const user = userEvent.setup();
    renderDialog();

    const form = dialog();
    await user.type(form.getByLabelText("Nome da quadra"), "Arena Nova");
    await user.type(form.getByLabelText("CEP"), "20541004");
    await waitFor(() => expect(geoCalls(fetchMock)).toHaveLength(1), { timeout: 2500 });

    await user.click(form.getByRole("button", { name: "Ajustar coordenadas manualmente" }));
    await user.type(form.getByLabelText("Latitude"), "-22.95");
    await user.type(form.getByLabelText("Longitude"), "-43.21");

    resolveLookup(
      jsonResponse(lookupResponse({ latitude: null, longitude: null, precision: "unresolved" })),
    );

    expect(
      await form.findByText(/Não foi possível obter as coordenadas deste CEP/),
    ).toBeInTheDocument();
    expect(form.getByLabelText("Latitude")).toHaveValue("-22.95");
    expect(form.getByLabelText("Longitude")).toHaveValue("-43.21");
  });

  it("mostra erro claro quando a consulta falha e mantém o ajuste manual disponível", async () => {
    stubApi(() => jsonResponse({ detail: { code: "geocoding_provider_error" } }, 502));
    const user = userEvent.setup();
    renderDialog();

    const form = dialog();
    await user.type(form.getByLabelText("Nome da quadra"), "Arena Nova");
    await user.type(form.getByLabelText("CEP"), "20541004");

    expect(
      await form.findByText(/serviço de CEP está indisponível agora/, undefined, {
        timeout: 2500,
      }),
    ).toBeInTheDocument();
    expect(form.getByRole("button", { name: "Ocultar ajuste manual" })).toBeInTheDocument();
  });
});
