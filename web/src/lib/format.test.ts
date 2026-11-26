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
    expect(formatError(new ApiError(422, "geocoding_unresolved"))).toBe(
      "Não foi possível obter as coordenadas deste CEP. Informe o ponto manualmente.",
    );
  });

  it("trata a compra de tickets desligada e o e-mail duplicado", () => {
    expect(formatError(new ApiError(503, "ticket_purchase_disabled"))).toBe(
      "A compra de tickets está temporariamente indisponível. Tente novamente mais tarde.",
    );
    expect(formatError(new ApiError(409, "email_already_exists"))).toBe(
      "Esse e-mail já está vinculado a outra conta. Use outro endereço.",
    );
    expect(formatError(new ApiError(403, "platform_admin_required"))).toBe(
      "Sua conta não tem permissão de administração da plataforma.",
    );
    expect(formatError(new ApiError(409, "format_in_use"))).toBe(
      "Esse formato já está em uso por reservas. Crie um novo formato para mudar o tamanho da equipe.",
    );
    expect(formatError(new ApiError(422, "pricing_not_configured"))).toBe(
      "O preço ainda não está configurado nas seis faixas. Configure o preço antes de salvar ou publicar.",
    );
    expect(formatError(new ApiError(409, "venue_not_publishable"))).toBe(
      "A quadra pública precisa de pelo menos um espaço ativo com preço configurado para ser publicada.",
    );
    expect(formatError(new ApiError(422, "geocoding_required"))).toBe(
      "Informe o CEP ou as coordenadas da quadra antes de publicar.",
    );
  });

  it("trata a renovação transitória sem anunciar sessão expirada", () => {
    expect(formatError(new ApiError(401, "refresh_retry_required"))).toBe("Renovando sessão…");
    expect(formatError(new ApiError(401, "account_suspended"))).toBe(
      "Sua conta está suspensa. Fale com o suporte para mais informações.",
    );
    expect(formatError(new ApiError(401, "invalid_refresh_token"))).toBe(
      "Sua sessão expirou. Entre novamente.",
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
