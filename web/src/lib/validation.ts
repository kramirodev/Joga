/**
 * Validação de entrada do painel.
 *
 * As regras espelham os limites dos schemas Pydantic do backend. Elas existem
 * para orientar antes do envio, nunca para substituir a validação do servidor.
 */

export interface TextRule {
  label: string;
  required?: boolean;
  min?: number;
  max?: number;
}

export function textError(value: string, rule: TextRule): string | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return rule.required === false ? null : `Informe ${rule.label}.`;
  }
  if (rule.min && trimmed.length < rule.min) {
    return `${capitalize(rule.label)} deve ter pelo menos ${rule.min} caracteres.`;
  }
  if (rule.max && trimmed.length > rule.max) {
    return `${capitalize(rule.label)} deve ter no máximo ${rule.max} caracteres.`;
  }
  return null;
}

export function requiredError(value: string, label: string): string | null {
  return value.trim() ? null : `Informe ${label}.`;
}

export function uuidError(value: string, label = "o UUID"): string | null {
  const trimmed = value.trim();
  if (!trimmed) return `Informe ${label}.`;
  if (
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(trimmed) &&
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(trimmed)
  ) {
    return "UUID inválido. Cole o identificador completo, com 36 caracteres.";
  }
  return null;
}

export function digitsOnly(value: string): string {
  return value.replace(/\D/g, "");
}

export function normalizeCnpj(value: string): string {
  return digitsOnly(value);
}

export function formatCnpj(value: string): string {
  const digits = digitsOnly(value).slice(0, 14);
  if (digits.length <= 2) return digits;
  if (digits.length <= 5) return `${digits.slice(0, 2)}.${digits.slice(2)}`;
  if (digits.length <= 8) {
    return `${digits.slice(0, 2)}.${digits.slice(2, 5)}.${digits.slice(5)}`;
  }
  if (digits.length <= 12) {
    return `${digits.slice(0, 2)}.${digits.slice(2, 5)}.${digits.slice(5, 8)}/${digits.slice(8)}`;
  }
  return `${digits.slice(0, 2)}.${digits.slice(2, 5)}.${digits.slice(5, 8)}/${digits.slice(
    8,
    12,
  )}-${digits.slice(12)}`;
}

/** Mesmo cálculo de dígitos verificadores do backend. */
export function isValidCnpj(value: string): boolean {
  const digits = normalizeCnpj(value);
  if (digits.length !== 14 || /^(\d)\1{13}$/.test(digits)) return false;
  const firstWeights = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
  const secondWeights = [6, ...firstWeights];
  for (const [weights, position] of [
    [firstWeights, 12],
    [secondWeights, 13],
  ] as const) {
    const total = digits
      .slice(0, position)
      .split("")
      .reduce((sum, digit, index) => sum + Number(digit) * weights[index], 0);
    const remainder = total % 11;
    const expected = remainder < 2 ? 0 : 11 - remainder;
    if (Number(digits[position]) !== expected) return false;
  }
  return true;
}

export function cnpjError(value: string, required = true): string | null {
  const digits = normalizeCnpj(value);
  if (!digits) return required ? "Informe o CNPJ." : null;
  if (digits.length !== 14) return "O CNPJ deve ter 14 dígitos.";
  if (!isValidCnpj(digits)) return "CNPJ inválido. Confira os dígitos.";
  return null;
}

export type PixKeyType = "cnpj" | "email" | "phone" | "random";

export function pixKeyError(type: PixKeyType, value: string): string | null {
  const raw = value.trim();
  if (!raw) return "Informe a chave Pix.";
  if (type === "cnpj") return cnpjError(raw);
  if (type === "email") {
    if (raw.length > 77) return "O e-mail deve ter no máximo 77 caracteres.";
    if (!/^[^@\s]+@[^@\s]+\.[a-z]{2,}$/i.test(raw)) return "E-mail inválido.";
    return null;
  }
  if (type === "phone") {
    const digits = digitsOnly(raw);
    if (!digits.startsWith("55") || digits.length < 12 || digits.length > 13) {
      return "Telefone Pix deve estar no formato +55 DDD número.";
    }
    return null;
  }
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(raw)) {
    return "Chave aleatória inválida. Use o formato UUID, com 36 caracteres.";
  }
  return null;
}

/** Converte texto monetário em centavos, aceitando ponto ou vírgula. */
export function moneyToCents(value: string): number | null {
  const cleaned = value.replace(/[R$\s]/g, "");
  if (!cleaned) return null;
  let normalized: string;
  const hasComma = cleaned.includes(",");
  if (hasComma) {
    normalized = cleaned.replace(/\./g, "").replace(",", ".");
  } else {
    const dots = cleaned.split(".");
    if (dots.length > 1 && dots[dots.length - 1].length === 2) {
      normalized = `${dots.slice(0, -1).join("")}.${dots[dots.length - 1]}`;
    } else {
      normalized = cleaned.replace(/\./g, "");
    }
  }
  const amount = Number(normalized);
  if (!Number.isFinite(amount)) return null;
  return Math.round(amount * 100);
}

export function moneyError(
  value: string,
  options: { label: string; minCents?: number; maxCents?: number; required?: boolean },
): string | null {
  const cents = moneyToCents(value);
  if (cents === null) {
    return options.required === false ? null : `Informe ${options.label}.`;
  }
  if (cents < 0 || (cents === 0 && options.minCents !== 0)) {
    return `${capitalize(options.label)} deve ser maior que zero.`;
  }
  if (options.minCents !== undefined && cents < options.minCents) {
    return `${capitalize(options.label)} não pode ser menor que ${formatCents(options.minCents)}.`;
  }
  if (options.maxCents !== undefined && cents > options.maxCents) {
    return `${capitalize(options.label)} não pode ultrapassar ${formatCents(options.maxCents)}.`;
  }
  return null;
}

export function formatCents(cents: number): string {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(cents / 100);
}

export function moneyInputFromCents(cents: number): string {
  return (cents / 100).toFixed(2).replace(".", ",");
}

export function normalizeMoneyInput(value: string): string {
  const cents = moneyToCents(value);
  return cents === null ? value : moneyInputFromCents(cents);
}

export function timeRangeError(start: string, end: string): string | null {
  if (!start) return "Informe o horário de início.";
  if (!end) return "Informe o horário de fim.";
  if (end <= start)
    return "O horário de fim deve ser depois do início. Janelas que cruzam a meia-noite não são aceitas.";
  return null;
}

export function dateRangeError(
  start: string,
  end: string,
  options: { requireFuture?: boolean } = {},
): string | null {
  if (!start) return "Informe o início.";
  if (!end) return "Informe o fim.";
  const startDate = new Date(start);
  const endDate = new Date(end);
  if (Number.isNaN(startDate.getTime())) return "Data/hora de início inválida.";
  if (Number.isNaN(endDate.getTime())) return "Data/hora de fim inválida.";
  if (endDate <= startDate) return "O fim deve ser depois do início.";
  if (options.requireFuture && endDate <= new Date()) {
    return "O período precisa terminar no futuro.";
  }
  return null;
}

export function coordinateError(
  latitude: string,
  longitude: string,
): {
  latitude?: string;
  longitude?: string;
} {
  const errors: { latitude?: string; longitude?: string } = {};
  if (!latitude.trim()) {
    errors.latitude = "Informe a latitude.";
  } else {
    const value = Number(latitude.replace(",", "."));
    if (!Number.isFinite(value) || value < -90 || value > 90) {
      errors.latitude = "Latitude deve estar entre -90 e 90.";
    }
  }
  if (!longitude.trim()) {
    errors.longitude = "Informe a longitude.";
  } else {
    const value = Number(longitude.replace(",", "."));
    if (!Number.isFinite(value) || value < -180 || value > 180) {
      errors.longitude = "Longitude deve estar entre -180 e 180.";
    }
  }
  return errors;
}

export function positiveIntegerError(
  value: number,
  min: number,
  max: number,
  label: string,
): string | null {
  if (!Number.isInteger(value)) return `${capitalize(label)} deve ser um número inteiro.`;
  if (value < min || value > max) return `${capitalize(label)} deve estar entre ${min} e ${max}.`;
  return null;
}

export function normalizeWhitespace(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

export const PHOTO_MAX_BYTES = 5_000_000;
export const PHOTO_ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"] as const;

export function photoFileError(file: { type: string; size: number } | null): string | null {
  if (!file) return "Selecione uma foto para enviar.";
  if (!PHOTO_ALLOWED_TYPES.includes(file.type as (typeof PHOTO_ALLOWED_TYPES)[number])) {
    return "Formato não aceito. Use JPEG, PNG ou WebP.";
  }
  if (file.size > PHOTO_MAX_BYTES) {
    return "A foto deve ter no máximo 5 MB.";
  }
  return null;
}

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export function firstErrorId(
  errors: Record<string, string | undefined>,
  order: string[],
): string | null {
  for (const field of order) {
    if (errors[field]) return field;
  }
  return null;
}
