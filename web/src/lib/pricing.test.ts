import { describe, expect, it } from "vitest";

import {
  minimumTickets,
  pricePerPlayerCents,
  requiredTotalCents,
  ticketsCoverInvariant,
  ticketsInvariantError,
} from "./pricing";

describe("tabela 2D — prévia do painel", () => {
  it("calcula o k mínimo e o preço por jogador nos dois modos", () => {
    expect(requiredTotalCents(12_000, "standard")).toBe(14_400);
    expect(requiredTotalCents(12_000, "contingency")).toBe(12_000);
    expect(minimumTickets(12_000, 5, "standard")).toBe(5);
    expect(minimumTickets(12_000, 5, "contingency")).toBe(4);
    expect(pricePerPlayerCents(5)).toBe(1_550);
  });

  it("confirma o invariante somente quando k cobre o total do modo", () => {
    expect(ticketsCoverInvariant(12_000, 5, 5, "standard")).toBe(true);
    expect(ticketsCoverInvariant(12_000, 5, 4, "standard")).toBe(false);
    expect(ticketsCoverInvariant(12_000, 5, 4, "contingency")).toBe(true);
    expect(ticketsInvariantError(12_000, 5, 1, "standard")).toBe(
      "Essa quantidade não cobre o preço no modo padrão. O mínimo para 5x5 é 5.",
    );
    expect(ticketsInvariantError(12_000, 5, 5, "standard")).toBeNull();
  });

  it("rejeita valores fora do intervalo inteiro", () => {
    expect(ticketsInvariantError(12_000, 5, 0, "standard")).toBe(
      "Informe um número inteiro de tickets entre 1 e 1.000.",
    );
    expect(ticketsInvariantError(12_000, 5, 1_001, "standard")).toBe(
      "Informe um número inteiro de tickets entre 1 e 1.000.",
    );
  });
});
