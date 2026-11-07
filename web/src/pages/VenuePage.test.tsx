import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthContext } from "../lib/auth-context";
import type { Organization, Role, Venue, VenuePhoto, VenueSpace } from "../types";
import { VenuePage } from "./VenuePage";

const organization: Organization = {
  id: "org-1",
  name: "Arena Tijuca",
  status: "active",
  role: "OWNER",
  created_at: "2026-11-01T12:00:00Z",
  updated_at: "2026-11-01T12:00:00Z",
};

const venue: Venue = {
  id: "venue-1",
  organization_id: "org-1",
  venue_id: null,
  name: "Arena Centro",
  city: "Rio de Janeiro",
  state: "RJ",
  address_line: null,
  timezone: "America/Sao_Paulo",
  status: "active",
  created_at: "2026-11-01T12:00:00Z",
  updated_at: "2026-11-01T12:00:00Z",
};

const space: VenueSpace = {
  id: "space-1",
  venue_id: "venue-1",
  name: "Quadra 1",
  description: "Coberta",
  status: "active",
  sports: [{ id: "sport-1", slug: "futebol", name: "Futebol" }],
  created_at: "2026-11-01T12:00:00Z",
  updated_at: "2026-11-01T12:00:00Z",
};

const photo: VenuePhoto = {
  id: "photo-1",
  venue_id: "venue-1",
  space_id: "space-1",
  status: "PENDING",
  content_type: "image/jpeg",
  size_bytes: 1200,
  width: 800,
  height: 600,
  caption: "Quadra coberta",
  rejection_reason: null,
  reviewed_by: null,
  reviewed_at: null,
  created_at: "2026-11-01T12:00:00Z",
  content_url: "/api/v1/organizations/org-1/venues/venue-1/photos/photo-1/content",
  can_review: false,
};

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function stubApi(role: Role, canReview: boolean) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/photos/photo-1/content")) {
      return new Response(new Blob([Uint8Array.from([0xff, 0xd8, 0xff])]), {
        status: 200,
        headers: { "Content-Type": "image/jpeg" },
      });
    }
    if (url.endsWith("/api/v1/organizations/org-1")) {
      return jsonResponse({ ...organization, role });
    }
    if (url.endsWith("/api/v1/organizations/org-1/venues/venue-1")) {
      return jsonResponse(venue);
    }
    if (url.endsWith("/venues/venue-1/spaces")) {
      return jsonResponse({ spaces: [space] });
    }
    if (url.endsWith("/api/v1/sports")) {
      return jsonResponse({
        sports: [
          {
            id: "sport-1",
            slug: "futebol",
            name: "Futebol",
            formats: [{ id: "format-1", slug: "futebol-5x5", name: "Futebol 5x5" }],
          },
        ],
      });
    }
    if (url.endsWith("/venues/venue-1/photos")) {
      return jsonResponse({ photos: [photo], can_review: canReview });
    }
    if (url.includes("/availability")) return jsonResponse({ availability: [] });
    if (url.includes("/blackouts")) return jsonResponse({ blackouts: [] });
    return jsonResponse({ detail: { code: "not_found" } });
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
      <MemoryRouter initialEntries={["/organizations/org-1/venues/venue-1"]}>
        <AuthContext.Provider
          value={{
            user: { id: "user-1", status: "active" },
            loading: false,
            signIn: vi.fn(),
            signOut: vi.fn(),
          }}
        >
          <Routes>
            <Route path="/organizations/:organizationId/venues/:venueId" element={<VenuePage />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("VenuePage — quadras, agenda e fotos", () => {
  it("operador vê quadras/agenda e não vê controles de revisão", async () => {
    stubApi("OPERATOR", false);
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByRole("heading", { name: "Arena Centro" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Quadra 1/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Salvar modalidades" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Agenda semanal" })).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: /Fotos/ }));
    expect(await screen.findByText("Em revisão")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Aprovar" })).not.toBeInTheDocument();
  });

  it("proprietário vê aprovação e rejeição de fotos", async () => {
    stubApi("OWNER", true);
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByRole("heading", { name: "Arena Centro" })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: /Fotos/ }));

    expect(await screen.findByRole("button", { name: "Aprovar" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Rejeitar" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remover" })).toBeInTheDocument();
  });
});
