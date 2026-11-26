import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "../../components/ui/Toast";
import type { Organization, PostalCodeLookup, Venue } from "../../types";
import { VenuesPanel } from "./VenuesPanel";

const organization: Organization = {
  id: "org-1",
  name: "Arena Tijuca",
  status: "active",
  role: "OWNER",
  cnpj: "11222333000181",
  cnpj_status: "ATIVA",
  verification_status: "verified",
  cnpj_verified_at: "2026-11-01T12:00:00Z",
  cnpj_next_check_at: "2026-11-08T12:00:00Z",
  payout_ready: true,
  payout_status: "active",
  pix_key_type: "cnpj",
  pix_key_masked: "****0001",
  created_at: "2026-11-01T12:00:00Z",
  updated_at: "2026-11-01T12:00:00Z",
};

const createdVenue: Venue = {
  id: "venue-new",
  organization_id: "org-1",
  venue_id: null,
  name: "Arena Nova",
  city: "Rio de Janeiro",
  state: "RJ",
  address_line: "Rua das Laranjeiras",
  latitude: -22.934,
  longitude: -43.201,
  postal_code: "20541004",
  geocoding_source: "brasilapi",
  geocoding_precision: "street",
  geocoded_at: "2026-11-01T12:00:00Z",
  timezone: "America/Sao_Paulo",
  status: "active",
  created_at: "2026-11-01T12:00:00Z",
  updated_at: "2026-11-01T12:00:00Z",
};

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

interface StubOptions {
  lookup?: (cep: string) => Promise<Response> | Response;
}

function stubApi(options: StubOptions = {}) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://joga.local");
    const path = url.pathname;
    if (path.startsWith("/api/v1/geo/postal-codes/")) {
      const cep = path.split("/").pop() ?? "";
      return options.lookup ? options.lookup(cep) : jsonResponse(lookupResponse());
    }
    if (path === "/api/v1/organizations/org-1/venues" && init?.method === "POST") {
      return jsonResponse(createdVenue, 201);
    }
    return jsonResponse({ detail: { code: "not_found" } }, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderPanel() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter>
          <VenuesPanel
            organization={organization}
            venues={[]}
            loading={false}
            error={null}
            onRetry={() => {}}
          />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function geoCalls(fetchMock: ReturnType<typeof stubApi>) {
  return fetchMock.mock.calls.filter(([url]) => String(url).includes("/geo/postal-codes/"));
}

function createCalls(fetchMock: ReturnType<typeof stubApi>) {
  return fetchMock.mock.calls.filter(
    ([url, init]) =>
      String(url).endsWith("/organizations/org-1/venues") &&
      (init as RequestInit | undefined)?.method === "POST",
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("VenuesPanel — cadastro de estabelecimento pelo CEP", () => {
  it("consulta o CEP automaticamente e preenche endereço e coordenadas recolhidas", async () => {
    const fetchMock = stubApi();
    const user = userEvent.setup();
    renderPanel();

    await user.type(screen.getByLabelText("Nome"), "Arena Nova");
    await user.type(screen.getByLabelText("CEP"), "20541004");

    await waitFor(() => expect(geoCalls(fetchMock)).toHaveLength(1), { timeout: 2500 });
    await waitFor(() => expect(screen.getByLabelText("Cidade")).toHaveValue("Rio de Janeiro"));
    expect(screen.getByLabelText("UF")).toHaveValue("RJ");
    expect(screen.getByLabelText("Endereço")).toHaveValue("Rua das Laranjeiras");
    expect(screen.getByText(/Endereço e coordenadas preenchidos pelo CEP/)).toBeInTheDocument();
    expect(screen.getByText(/Coordenadas: -22\.934, -43\.201/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ajustar coordenadas manualmente" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(screen.queryByLabelText("Latitude")).not.toBeInTheDocument();
    expect(geoCalls(fetchMock)).toHaveLength(1);
  });

  it("abre o ajuste manual quando o CEP não traz coordenadas e bloqueia o envio sem o ponto", async () => {
    const fetchMock = stubApi({
      lookup: () =>
        jsonResponse(lookupResponse({ latitude: null, longitude: null, precision: "unresolved" })),
    });
    const user = userEvent.setup();
    renderPanel();

    await user.type(screen.getByLabelText("Nome"), "Arena Nova");
    await user.type(screen.getByLabelText("CEP"), "20541004");

    expect(
      await screen.findByText(/Não foi possível obter as coordenadas deste CEP/, undefined, {
        timeout: 2500,
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ocultar ajuste manual" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    expect(screen.getByLabelText("Latitude")).toHaveValue("");
    expect(screen.getByLabelText("Longitude")).toHaveValue("");

    await user.click(screen.getByRole("button", { name: "Cadastrar estabelecimento" }));
    expect(await screen.findByText("Informe a latitude.")).toBeInTheDocument();
    expect(createCalls(fetchMock)).toHaveLength(0);

    await user.type(screen.getByLabelText("Latitude"), "-22.95");
    await user.type(screen.getByLabelText("Longitude"), "-43.21");
    await user.click(screen.getByRole("button", { name: "Cadastrar estabelecimento" }));

    await waitFor(() => expect(createCalls(fetchMock)).toHaveLength(1));
    const body = JSON.parse(String((createCalls(fetchMock)[0][1] as RequestInit).body));
    expect(body.latitude).toBe(-22.95);
    expect(body.longitude).toBe(-43.21);
    expect(body).not.toHaveProperty("geocoding_source");
    expect(body).not.toHaveProperty("geocoding_precision");
  });

  it("preserva coordenadas digitadas manualmente quando o CEP volta sem coordenadas", async () => {
    let resolveLookup: (response: Response) => void = () => {};
    const pending = new Promise<Response>((resolve) => {
      resolveLookup = resolve;
    });
    const fetchMock = stubApi({ lookup: () => pending });
    const user = userEvent.setup();
    renderPanel();

    await user.type(screen.getByLabelText("Nome"), "Arena Nova");
    await user.type(screen.getByLabelText("CEP"), "20541004");
    await waitFor(() => expect(geoCalls(fetchMock)).toHaveLength(1), { timeout: 2500 });

    await user.click(screen.getByRole("button", { name: "Ajustar coordenadas manualmente" }));
    await user.type(screen.getByLabelText("Latitude"), "-22.95");
    await user.type(screen.getByLabelText("Longitude"), "-43.21");

    resolveLookup(
      jsonResponse(lookupResponse({ latitude: null, longitude: null, precision: "unresolved" })),
    );

    expect(
      await screen.findByText(/Não foi possível obter as coordenadas deste CEP/),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Latitude")).toHaveValue("-22.95");
    expect(screen.getByLabelText("Longitude")).toHaveValue("-43.21");
  });

  it("limpa as coordenadas automáticas ao trocar o CEP e preenche com o novo endereço", async () => {
    stubApi({
      lookup: (cep) =>
        jsonResponse(
          cep === "24020000"
            ? lookupResponse({
                postal_code: "24020000",
                street: "Rua do Comércio",
                city: "Niterói",
                latitude: -22.883,
                longitude: -43.103,
              })
            : lookupResponse(),
        ),
    });
    const user = userEvent.setup();
    renderPanel();

    await user.type(screen.getByLabelText("Nome"), "Arena Nova");
    await user.type(screen.getByLabelText("CEP"), "20541004");
    await waitFor(
      () => expect(screen.getByText(/Coordenadas: -22\.934, -43\.201/)).toBeInTheDocument(),
      {
        timeout: 2500,
      },
    );

    await user.clear(screen.getByLabelText("CEP"));
    await user.type(screen.getByLabelText("CEP"), "24020000");

    // A coordenada do CEP anterior não pode continuar valendo para o novo CEP.
    expect(screen.queryByText(/Coordenadas: -22\.934/)).not.toBeInTheDocument();

    await waitFor(() => expect(screen.getByLabelText("Cidade")).toHaveValue("Niterói"), {
      timeout: 2500,
    });
    expect(screen.getByLabelText("Endereço")).toHaveValue("Rua do Comércio");
    expect(screen.getByText(/Coordenadas: -22\.883, -43\.103/)).toBeInTheDocument();
    expect(screen.queryByText(/-22\.934/)).not.toBeInTheDocument();
  });

  it("descarta a resposta atrasada de um CEP que já foi trocado", async () => {
    let resolveFirst: (response: Response) => void = () => {};
    const first = new Promise<Response>((resolve) => {
      resolveFirst = resolve;
    });
    const fetchMock = stubApi({
      lookup: (cep) => {
        if (cep === "20541004") return first;
        return jsonResponse(
          lookupResponse({
            postal_code: "24020000",
            street: "Rua do Comércio",
            city: "Niterói",
            latitude: -22.883,
            longitude: -43.103,
          }),
        );
      },
    });
    const user = userEvent.setup();
    renderPanel();

    await user.type(screen.getByLabelText("Nome"), "Arena Nova");
    await user.type(screen.getByLabelText("CEP"), "20541004");
    await waitFor(() => expect(geoCalls(fetchMock)).toHaveLength(1), { timeout: 2500 });

    await user.clear(screen.getByLabelText("CEP"));
    await user.type(screen.getByLabelText("CEP"), "24020000");
    resolveFirst(jsonResponse(lookupResponse()));

    await waitFor(() => expect(screen.getByLabelText("Cidade")).toHaveValue("Niterói"), {
      timeout: 2500,
    });
    expect(screen.getByLabelText("Endereço")).toHaveValue("Rua do Comércio");
    expect(screen.queryByText(/Rua das Laranjeiras/)).not.toBeInTheDocument();
    expect(screen.queryByText(/-22\.934/)).not.toBeInTheDocument();
  });

  it("mostra erro claro quando a consulta falha e permite informar o ponto manualmente", async () => {
    stubApi({
      lookup: () => jsonResponse({ detail: { code: "geocoding_timeout" } }, 504),
    });
    const user = userEvent.setup();
    renderPanel();

    await user.type(screen.getByLabelText("Nome"), "Arena Nova");
    await user.type(screen.getByLabelText("CEP"), "20541004");

    expect(
      await screen.findByText(/serviço de CEP demorou para responder/, undefined, {
        timeout: 2500,
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ocultar ajuste manual" })).toBeInTheDocument();
    expect(screen.getByLabelText("Latitude")).toBeInTheDocument();
  });

  it("mantém a proveniência do CEP quando as coordenadas não são alteradas", async () => {
    const fetchMock = stubApi();
    const user = userEvent.setup();
    renderPanel();

    await user.type(screen.getByLabelText("Nome"), "Arena Nova");
    await user.type(screen.getByLabelText("CEP"), "20541004");
    await waitFor(() => expect(geoCalls(fetchMock)).toHaveLength(1), { timeout: 2500 });
    await waitFor(() => expect(screen.getByLabelText("Cidade")).toHaveValue("Rio de Janeiro"));

    await user.click(screen.getByRole("button", { name: "Cadastrar estabelecimento" }));
    await waitFor(() => expect(createCalls(fetchMock)).toHaveLength(1));
    const body = JSON.parse(String((createCalls(fetchMock)[0][1] as RequestInit).body));
    expect(body.geocoding_source).toBe("brasilapi");
    expect(body.geocoding_precision).toBe("street");
    expect(body.latitude).toBeCloseTo(-22.934);
  });

  it("não envia proveniência de CEP depois de ajustar as coordenadas manualmente", async () => {
    const fetchMock = stubApi();
    const user = userEvent.setup();
    renderPanel();

    await user.type(screen.getByLabelText("Nome"), "Arena Nova");
    await user.type(screen.getByLabelText("CEP"), "20541004");
    await waitFor(() => expect(geoCalls(fetchMock)).toHaveLength(1), { timeout: 2500 });
    await waitFor(() => expect(screen.getByLabelText("Cidade")).toHaveValue("Rio de Janeiro"));

    await user.click(screen.getByRole("button", { name: "Ajustar coordenadas manualmente" }));
    const latitude = screen.getByLabelText("Latitude");
    await user.clear(latitude);
    await user.type(latitude, "-22.95");
    await user.click(screen.getByRole("button", { name: "Cadastrar estabelecimento" }));

    await waitFor(() => expect(createCalls(fetchMock)).toHaveLength(1));
    const body = JSON.parse(String((createCalls(fetchMock)[0][1] as RequestInit).body));
    expect(body.latitude).toBe(-22.95);
    expect(body).not.toHaveProperty("geocoding_source");
    expect(body).not.toHaveProperty("geocoding_precision");
  });
});
