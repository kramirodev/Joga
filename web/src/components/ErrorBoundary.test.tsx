import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { resetTelemetryForTests } from "../lib/telemetry";
import { ErrorBoundary } from "./ErrorBoundary";

function Boom(): never {
  throw new Error("falha simulada");
}

describe("ErrorBoundary", () => {
  beforeEach(() => {
    resetTelemetryForTests();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("mostra fallback e registra o erro no console", () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(null, { status: 202 })),
    );

    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
      "O painel encontrou um erro inesperado. Recarregue a página.",
    );
    expect(consoleSpy).toHaveBeenCalledWith(
      "joga.panel.render_error",
      expect.any(Error),
      expect.anything(),
    );
  });

  it("reporta o erro de renderização com o empilhamento de componentes", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const fetchMock = vi.fn(async () => new Response(null, { status: 202 }));
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    const body = JSON.parse(String(init.body)) as {
      events: Array<{ message: string; module: string; stack?: string; platform: string }>;
    };
    const event = body.events[0]!;
    expect(event.message).toBe("falha simulada");
    expect(event.module).toBe("error-boundary");
    expect(event.platform).toBe("web");
    expect(event.stack).toContain("Boom");
  });
});
