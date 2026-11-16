import { describe, expect, it } from "vitest";

import {
  cnpjError,
  coordinateError,
  dateRangeError,
  formatCnpj,
  isValidCnpj,
  moneyError,
  moneyInputFromCents,
  moneyToCents,
  normalizeMoneyInput,
  pixKeyError,
  photoFileError,
  textError,
  timeRangeError,
  uuidError,
} from "./validation";

describe("validation", () => {
  it("valida limites de texto com mensagens específicas", () => {
    expect(textError("", { label: "o nome", max: 120 })).toBe("Informe o nome.");
    expect(textError("a", { label: "o nome", min: 2, max: 120 })).toMatch(/pelo menos 2/);
    expect(textError("a".repeat(121), { label: "o nome", max: 120 })).toMatch(/no máximo 120/);
    expect(textError("  Arena  ", { label: "o nome", min: 2, max: 120 })).toBeNull();
  });

  it("valida e formata CNPJ pelos dígitos verificadores", () => {
    expect(isValidCnpj("11222333000181")).toBe(true);
    expect(isValidCnpj("12.345.678/0001-99")).toBe(false);
    expect(cnpjError("11222333000181")).toBeNull();
    expect(cnpjError("123")).toMatch(/14 dígitos/);
    expect(formatCnpj("11222333000181")).toBe("11.222.333/0001-81");
  });

  it("converte valores monetários em centavos", () => {
    expect(moneyToCents("120")).toBe(12000);
    expect(moneyToCents("120,50")).toBe(12050);
    expect(moneyToCents("1.234,56")).toBe(123456);
    expect(moneyToCents("120.50")).toBe(12050);
    expect(moneyToCents("R$ 99,90")).toBe(9990);
    expect(moneyToCents("")).toBeNull();
    expect(normalizeMoneyInput("120")).toBe("120,00");
    expect(moneyInputFromCents(40000)).toBe("400,00");
  });

  it("valida teto de preço da faixa", () => {
    expect(moneyError("300,00", { label: "o preço", maxCents: 30000 })).toBeNull();
    expect(moneyError("300,01", { label: "o preço", maxCents: 30000 })).toMatch(/ultrapassar/);
    expect(moneyError("0", { label: "o preço" })).toMatch(/maior que zero/);
    expect(moneyError("", { label: "o preço" })).toBe("Informe o preço.");
  });

  it("valida chave Pix por tipo", () => {
    expect(pixKeyError("cnpj", "11.222.333/0001-81")).toBeNull();
    expect(pixKeyError("email", "financeiro@arena.com.br")).toBeNull();
    expect(pixKeyError("email", "sem-arroba")).toMatch(/E-mail inválido/);
    expect(pixKeyError("phone", "+5511987654321")).toBeNull();
    expect(pixKeyError("phone", "+351912345678")).toMatch(/formato \+55/);
    expect(pixKeyError("random", "00000000-0000-0000-0000-000000000000")).toBeNull();
  });

  it("valida intervalos de horário e data", () => {
    expect(timeRangeError("18:00", "22:00")).toBeNull();
    expect(timeRangeError("22:00", "18:00")).toMatch(/depois do início/);
    expect(dateRangeError("2026-11-14T10:00", "2026-11-14T12:00")).toBeNull();
    expect(dateRangeError("2026-11-14T12:00", "2026-11-14T10:00")).toMatch(/depois do início/);
  });

  it("valida coordenadas geográficas", () => {
    expect(coordinateError("-22.9", "-43.2")).toEqual({});
    expect(coordinateError("-90", "-180")).toEqual({});
    expect(coordinateError("91", "-43.2").latitude).toMatch(/entre -90 e 90/);
    expect(coordinateError("-22.9", "-181").longitude).toMatch(/entre -180 e 180/);
  });

  it("valida UUID sem confundir formatos", () => {
    expect(uuidError("00000000-0000-4000-8000-000000000000")).toBeNull();
    expect(uuidError("user-1")).toMatch(/UUID inválido/);
  });

  it("valida tipo e tamanho da foto antes do upload", () => {
    expect(photoFileError(null)).toMatch(/Selecione uma foto/);
    expect(photoFileError({ type: "text/plain", size: 10 })).toMatch(/Formato não aceito/);
    expect(photoFileError({ type: "image/png", size: 5_000_001 })).toMatch(/5 MB/);
    expect(photoFileError({ type: "image/jpeg", size: 5_000_000 })).toBeNull();
  });
});
