import { describe, expect, it } from "vitest";

import { ApiError } from "./api";
import {
  formatDateRange,
  formatDay,
  formatError,
  formatRelative,
  formatTime,
  precisionLabel,
} from "./format";

describe("format", () => {
  it("formata horários no fuso do estabelecimento", () => {
    expect(formatDay("2026-11-15T23:00:00Z", "America/Sao_Paulo")).toBe("15 de nov. de 2026");
    expect(formatTime("2026-11-15T23:00:00Z", "America/Sao_Paulo")).toBe("20:00");
    expect(formatTime("2026-11-16T01:00:00Z", "America/Sao_Paulo")).toBe("22:00");
  });

  it("considera o mesmo dia no fuso do estabelecimento", () => {
    const range = formatDateRange(
      "2026-11-15T23:00:00Z",
      "2026-11-16T01:00:00Z",
      "America/Sao_Paulo",
    );
    expect(range).toBe("15 de nov. de 2026, 20:00–22:00");
  });

  it("usa fallback quando o fuso é inválido", () => {
    expect(() =>
      formatDateRange("2026-11-15T23:00:00Z", "2026-11-16T01:00:00Z", "Fuso/Inválido"),
    ).not.toThrow();
  });

  it("expõe mensagens de validação do backend", () => {
    const error = new ApiError(422, "validation_error", "Dados inválidos", "req-1", [
      { field: "query.limit", code: "less_than_equal", message: "Limite máximo é 100." },
    ]);
    expect(formatError(error)).toBe("Dados inválidos: Limite máximo é 100.");
  });

  it("formata notificações em tempo relativo", () => {
    const now = Date.parse("2026-11-15T12:00:00Z");
    expect(formatRelative("2026-11-15T11:58:00Z", now)).toBe("há 2 minutos");
    expect(formatRelative("2026-11-15T09:00:00Z", now)).toBe("há 3 horas");
    expect(formatRelative("2026-11-01T12:00:00Z", now)).toMatch(/^01\/11\/2026/);
  });

  it("traduz a precisão do CEP e os erros de geocodificação", () => {
    expect(precisionLabel("street")).toBe("Rua");
    expect(precisionLabel("approximate")).toBe("Aproximada");
    expect(precisionLabel("unresolved")).toBe("Sem coordenada");
    expect(formatError(new ApiError(404, "postal_code_not_found"))).toBe(
      "Não encontramos esse CEP. Confira os dígitos ou informe o endereço manualmente.",
    );
    expect(formatError(new ApiError(504, "geocoding_timeout"))).toBe(
      "O serviço de CEP demorou para responder. Tente novamente em instantes.",
    );
  });

  it("informa o tempo exato de espera em rate_limited", () => {
    expect(formatError(new ApiError(429, "rate_limited", undefined, null, [], 45))).toBe(
      "Muitas tentativas. Tente novamente em 45 segundos.",
    );
    expect(formatError(new ApiError(429, "rate_limited", undefined, null, [], 120))).toBe(
      "Muitas tentativas. Tente novamente em 2 minutos.",
    );
    expect(formatError(new ApiError(429, "rate_limited"))).toBe(
      "Muitas tentativas. Aguarde um instante e tente novamente.",
    );
  });
});
