import { ApiError } from "./api";
import type { Role } from "../types";

export function roleLabel(role: Role): string {
  switch (role) {
    case "OWNER":
      return "Proprietário";
    case "ADMIN":
      return "Administrador";
    case "OPERATOR":
      return "Operador";
  }
}

export function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}

export function formatError(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return "Não foi possível concluir a operação. Tente novamente.";
  }

  switch (error.code) {
    case "invalid_phone":
      return "Telefone inválido. Use o formato com DDD.";
    case "rate_limited":
      return "Muitas tentativas. Aguarde alguns minutos e tente novamente.";
    case "invalid_code_or_challenge":
      return "Código inválido ou expirado. Solicite um novo código.";
    case "invalid_receipt":
      return "A verificação expirou. Solicite um novo código.";
    case "account_not_found":
      return "Não encontramos uma conta com esse telefone. Crie uma conta para continuar.";
    case "phone_already_registered":
      return "Esse telefone já possui conta. Use a opção Entrar.";
    case "forbidden":
      return "Seu papel não permite esta ação.";
    case "role_not_allowed":
      return "Seu papel não permite gerenciar esse membro.";
    case "last_owner_required":
      return "A organização precisa de pelo menos um proprietário.";
    case "member_already_exists":
      return "Esse usuário já é membro da organização.";
    case "user_not_found":
      return "Usuário não encontrado.";
    case "user_not_active":
      return "Esse usuário não está ativo.";
    case "organization_not_found":
      return "Organização não encontrada ou fora do seu acesso.";
    case "venue_not_found":
      return "Estabelecimento não encontrado ou fora do seu acesso.";
    case "csrf_failed":
      return "Sessão inválida. Recarregue a página e entre novamente.";
    case "invalid_refresh_token":
    case "refresh_reuse_detected":
      return "Sua sessão expirou. Entre novamente.";
    case "invalid_token":
      return "Sua sessão expirou. Entre novamente.";
    case "request_failed":
      return error.message;
    default:
      return error.message || "Não foi possível concluir a operação.";
  }
}
