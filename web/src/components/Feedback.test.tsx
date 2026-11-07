import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ErrorNotice } from "./Feedback";

describe("ErrorNotice", () => {
  it("exibe a referência de suporte quando disponível", () => {
    render(<ErrorNotice message="Falha ao carregar." requestId="req-abc-123" />);

    expect(screen.getByRole("alert")).toHaveTextContent("Falha ao carregar.");
    expect(screen.getByText("req-abc-123")).toBeInTheDocument();
  });

  it("não exibe referência quando o erro não tem request ID", () => {
    render(<ErrorNotice message="Falha ao carregar." />);

    expect(screen.queryByText(/Referência para suporte/)).not.toBeInTheDocument();
  });
});
