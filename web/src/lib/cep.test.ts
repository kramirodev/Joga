import { describe, expect, it } from "vitest";

import { cepError, formatCep, normalizeCep } from "./cep";

describe("CEP", () => {
  it("normaliza para dígitos e limita a oito", () => {
    expect(normalizeCep("20.541-004")).toBe("20541004");
    expect(normalizeCep("20541004999")).toBe("20541004");
    expect(normalizeCep("abc")).toBe("");
  });

  it("formata com hífen a partir do sexto dígito", () => {
    expect(formatCep("20541004")).toBe("20541-004");
    expect(formatCep("20541")).toBe("20541");
    expect(formatCep("2054100")).toBe("20541-00");
  });

  it("valida o CEP", () => {
    expect(cepError("20541-004")).toBeNull();
    expect(cepError("")).toBe("Informe o CEP do estabelecimento.");
    expect(cepError("2054")).toBe("O CEP precisa ter oito dígitos.");
    expect(cepError("00000000")).toBe("Informe um CEP válido.");
  });
});
