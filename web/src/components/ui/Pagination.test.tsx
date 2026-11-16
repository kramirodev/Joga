import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Pagination } from "./Pagination";

describe("Pagination", () => {
  it("mostra o intervalo e navega por offset", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<Pagination total={120} limit={50} offset={50} onChange={onChange} />);

    expect(screen.getByText("Mostrando 51–100 de 120")).toBeInTheDocument();
    expect(screen.getByText("Página 2 de 3")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Anterior" }));
    expect(onChange).toHaveBeenCalledWith(0);

    await user.click(screen.getByRole("button", { name: "Próxima" }));
    expect(onChange).toHaveBeenCalledWith(100);
  });

  it("desabilita os botões nos limites", () => {
    const { rerender } = render(<Pagination total={10} limit={50} offset={0} onChange={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Próxima" })).toBeDisabled();

    rerender(<Pagination total={0} limit={50} offset={0} onChange={vi.fn()} />);
    expect(screen.queryByRole("navigation", { name: "Paginação" })).not.toBeInTheDocument();
  });
});
