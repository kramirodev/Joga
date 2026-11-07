import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ErrorBoundary } from "./ErrorBoundary";

function Boom(): never {
  throw new Error("falha simulada");
}

describe("ErrorBoundary", () => {
  it("mostra fallback e registra o erro no console", () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

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
});
