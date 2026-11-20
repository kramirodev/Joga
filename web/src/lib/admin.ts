import { ApiError } from "./api";
import { formatError } from "./format";

export function isForbidden(error: unknown): boolean {
  return error instanceof ApiError && error.status === 403;
}

/** 403 na área administrativa tem mensagem própria, não a genérica de papel. */
export function adminErrorMessage(error: unknown): string {
  return isForbidden(error)
    ? "Sua conta não tem permissão de administração da plataforma."
    : formatError(error);
}
