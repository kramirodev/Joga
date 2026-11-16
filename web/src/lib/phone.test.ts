import { describe, expect, it } from "vitest";

import {
  COUNTRIES,
  DEFAULT_COUNTRY,
  findCountry,
  formatE164ForDisplay,
  formatNational,
  parseInternationalInput,
  phoneError,
  toE164,
} from "./phone";

describe("phone", () => {
  it("formata celular brasileiro e devolve E.164 sem +55 manual", () => {
    expect(formatNational(DEFAULT_COUNTRY, "11987654321")).toBe("11 98765-4321");
    expect(toE164(DEFAULT_COUNTRY, "11987654321")).toBe("+5511987654321");
    expect(phoneError(DEFAULT_COUNTRY, "11987654321")).toBeNull();
  });

  it("formata telefone fixo brasileiro com 10 dígitos", () => {
    expect(formatNational(DEFAULT_COUNTRY, "1134567890")).toBe("11 3456-7890");
    expect(phoneError(DEFAULT_COUNTRY, "1134567890")).toBeNull();
  });

  it("rejeita DDD e celular brasileiro inválidos", () => {
    expect(phoneError(DEFAULT_COUNTRY, "01987654321")).toMatch(/DDD inválido/);
    expect(phoneError(DEFAULT_COUNTRY, "11887654321")).toMatch(/primeiro dígito/);
    expect(phoneError(DEFAULT_COUNTRY, "1198765432")).toMatch(/Faltou um dígito/);
  });

  it("aceita número internacional com máscara local", () => {
    const portugal = findCountry("PT");
    expect(toE164(portugal, "912345678")).toBe("+351912345678");
    expect(formatNational(portugal, "912345678")).toBe("912 345 678");
    expect(phoneError(portugal, "912345678")).toBeNull();
  });

  it("identifica país ao colar número em formato internacional", () => {
    const parsed = parseInternationalInput("+351 912 345 678");
    expect(parsed?.country.code).toBe("PT");
    expect(parsed?.nationalDigits).toBe("912345678");

    const brazil = parseInternationalInput("0055 (11) 98765-4321");
    expect(brazil?.country.code).toBe("BR");
    expect(brazil?.nationalDigits).toBe("11987654321");
  });

  it("não trata número local sem prefixo como internacional", () => {
    expect(parseInternationalInput("11987654321")).toBeNull();
  });

  it("exibe o número em formato legível", () => {
    expect(formatE164ForDisplay("+5511987654321")).toBe("+55 11 98765-4321");
  });

  it("mantém a lista de países sem códigos duplicados", () => {
    const codes = COUNTRIES.map((country) => country.code);
    expect(new Set(codes).size).toBe(codes.length);
  });
});
