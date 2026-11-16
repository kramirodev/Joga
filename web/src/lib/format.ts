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

const validTimeZones = new Map<string, boolean>();

function safeTimeZone(timeZone?: string | null): string | undefined {
  if (!timeZone) return undefined;
  const known = validTimeZones.get(timeZone);
  if (known === false) return undefined;
  if (known === true) return timeZone;
  try {
    new Intl.DateTimeFormat("pt-BR", { timeZone });
    validTimeZones.set(timeZone, true);
    return timeZone;
  } catch {
    validTimeZones.set(timeZone, false);
    return undefined;
  }
}

export function formatDate(value: string, timeZone?: string | null): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: safeTimeZone(timeZone),
  }).format(date);
}

export function formatDay(value: string, timeZone?: string | null): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "medium",
    timeZone: safeTimeZone(timeZone),
  }).format(date);
}

export function formatTime(value: string, timeZone?: string | null): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("pt-BR", {
    timeStyle: "short",
    timeZone: safeTimeZone(timeZone),
  }).format(date);
}

export function formatDateRange(
  startsAt: string,
  endsAt: string,
  timeZone?: string | null,
): string {
  const start = new Date(startsAt);
  const end = new Date(endsAt);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
    return `${formatDate(startsAt, timeZone)} — ${formatDate(endsAt, timeZone)}`;
  }
  const sameDay = formatDay(startsAt, timeZone) === formatDay(endsAt, timeZone);
  if (sameDay) {
    return `${formatDay(startsAt, timeZone)}, ${formatTime(startsAt, timeZone)}–${formatTime(
      endsAt,
      timeZone,
    )}`;
  }
  return `${formatDate(startsAt, timeZone)} — ${formatDate(endsAt, timeZone)}`;
}

export function formatMoney(cents: number): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(cents / 100);
}

export function shortId(value: string): string {
  return value.length > 10 ? value.slice(0, 8) : value;
}

export function initials(name: string | null | undefined): string {
  const clean = (name ?? "").trim();
  if (!clean) return "?";
  const parts = clean.split(/\s+/);
  return `${parts[0]?.[0] ?? ""}${parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? "") : ""}`.toUpperCase();
}

export function requestIdOf(error: unknown): string | null {
  return error instanceof ApiError ? error.requestId : null;
}

const BOOKING_STATUS: Record<string, string> = {
  PARTICIPANT_CONFIRMATION: "Confirmação dos jogadores",
  REQUESTED: "Aguardando o estabelecimento",
  DECLINED: "Recusada",
  EXPIRED: "Expirada",
  HOLD_CONFIRMED: "Bloqueio confirmado",
  PAYMENT_PENDING: "Aguardando pagamentos",
  CONFIRMED: "Confirmada",
  CANCELLED: "Cancelada",
  CANCELLED_BY_VENUE: "Cancelada pelo estabelecimento",
  CANCELLED_BY_PLAYER: "Cancelada pelo jogador",
  SUBSTITUTING: "Em substituição",
  COMPLETED: "Concluída",
};

const PAYMENT_STATUS: Record<string, string> = {
  PENDING: "Pagamento pendente",
  PAID: "Pago",
  REFUNDED: "Reembolsado",
  FAILED: "Falhou",
  WAIVED: "Isento",
  EXPIRED: "Expirado",
  CANCELLED: "Cancelado",
};

const PRESENCE_STATUS: Record<string, string> = {
  PENDING: "Presença pendente",
  PRESENT: "Presente",
  UNVERIFIED: "A confirmar",
  NO_SHOW: "Não compareceu",
};

const TIMER_TYPE: Record<string, string> = {
  T1: "Confirmação dos jogadores",
  T2: "Resposta do estabelecimento",
  T3: "Pagamento e bloqueio",
};

const TIMER_STATUS: Record<string, string> = {
  RUNNING: "em andamento",
  COMPLETED: "concluído",
  EXPIRED: "expirado",
  CANCELLED: "cancelado",
};

const RELEASE_STATUS: Record<string, string> = {
  PENDING: "A repassar",
  RELEASED: "Repassado",
  FAILED: "Falhou",
  REVERSED: "Revertido",
};

const HOLD_STATUS: Record<string, string> = {
  ACTIVE: "Bloqueio ativo",
  RELEASED: "Bloqueio liberado",
  EXPIRED: "Bloqueio expirado",
};

const DISPUTE_STATUS: Record<string, string> = {
  OPEN: "Em análise",
  ACCEPTED: "Procedente",
  REJECTED: "Improcedente",
  WITHDRAWN: "Retirada",
};

const LEDGER_ENTRY: Record<string, string> = {
  CHARGE_CREATED: "Cobrança criada",
  PAYMENT_CONFIRMED: "Pagamento confirmado",
  PAYMENT_REFUNDED: "Reembolso",
  VENUE_RELEASE: "Repasse ao estabelecimento",
};

const ORGANIZATION_STATUS: Record<string, string> = {
  active: "Ativa",
  suspended: "Suspensa",
  closed: "Encerrada",
};

const PAYOUT_STATUS: Record<string, string> = {
  pending: "Cadastro pendente",
  active: "Cadastro ativo",
  blocked: "Bloqueado",
};

const SPACE_STATUS: Record<string, string> = {
  active: "Ativa",
  inactive: "Inativa",
};

const AUDIT_ACTION: Record<string, string> = {
  "organization.created": "Organização criada",
  "organization.updated": "Organização atualizada",
  "organization.payout_updated": "Destino de repasse atualizado",
  "membership.added": "Membro adicionado",
  "membership.role_changed": "Papel de membro alterado",
  "membership.removed": "Membro removido",
  "venue.created": "Estabelecimento criado",
  "venue.updated": "Estabelecimento atualizado",
  "venue_space.created": "Quadra criada",
  "venue_space.updated": "Quadra atualizada",
  "venue_space.deleted": "Quadra removida",
  "venue_space.sports_replaced": "Modalidades da quadra atualizadas",
  "venue_availability.created": "Janela de agenda criada",
  "venue_availability.updated": "Janela de agenda atualizada",
  "venue_availability.deleted": "Janela de agenda removida",
  "venue_blackout.created": "Bloqueio criado",
  "venue_blackout.deleted": "Bloqueio removido",
  "venue_business_hour.created": "Expediente criado",
  "venue_business_hour.deleted": "Expediente removido",
  "venue_closure.created": "Fechamento criado",
  "venue_closure.deleted": "Fechamento removido",
  "venue_photo.uploaded": "Foto enviada",
  "venue_photo.reviewed": "Foto revisada",
  "venue_photo.removed": "Foto removida",
};

const AUDIT_RESOURCE: Record<string, string> = {
  organization: "Organização",
  venue: "Estabelecimento",
  venue_space: "Quadra",
  venue_availability: "Janela de agenda",
  venue_blackout: "Bloqueio",
  venue_business_hour: "Expediente",
  venue_closure: "Fechamento",
  venue_photo: "Foto",
  membership: "Vínculo",
};

export function bookingStatusLabel(status: string): string {
  return BOOKING_STATUS[status] ?? status;
}

export function paymentStatusLabel(status: string): string {
  return PAYMENT_STATUS[status] ?? status;
}

export function presenceStatusLabel(status: string): string {
  return PRESENCE_STATUS[status] ?? status;
}

export function timerTypeLabel(type: string): string {
  return TIMER_TYPE[type] ?? type;
}

export function timerStatusLabel(status: string): string {
  return TIMER_STATUS[status] ?? status;
}

export function releaseStatusLabel(status: string): string {
  return RELEASE_STATUS[status] ?? status;
}

export function holdStatusLabel(status: string): string {
  return HOLD_STATUS[status] ?? status;
}

export function disputeStatusLabel(status: string): string {
  return DISPUTE_STATUS[status] ?? status;
}

export function ledgerEntryLabel(type: string): string {
  return LEDGER_ENTRY[type] ?? type;
}

export function organizationStatusLabel(status: string): string {
  return ORGANIZATION_STATUS[status] ?? status;
}

export function payoutStatusLabel(status: string): string {
  return PAYOUT_STATUS[status] ?? status;
}

export function spaceStatusLabel(status: string): string {
  return SPACE_STATUS[status] ?? status;
}

export function auditActionLabel(action: string): string {
  return AUDIT_ACTION[action] ?? action;
}

export function auditResourceLabel(type: string): string {
  return AUDIT_RESOURCE[type] ?? type;
}

export function settledWithLabel(value: string): string {
  return value === "tickets" ? "Ingressos" : value === "pix" ? "Pix" : value;
}

export function precisionLabel(precision: string): string {
  switch (precision) {
    case "street":
      return "Rua";
    case "venue":
      return "Estabelecimento";
    case "approximate":
      return "Aproximada";
    case "unresolved":
      return "Sem coordenada";
    case "manual":
      return "Manual";
    default:
      return precision;
  }
}

function formatWait(seconds: number): string {
  if (seconds <= 1) return "1 segundo";
  if (seconds < 60) return `${seconds} segundos`;
  const minutes = Math.ceil(seconds / 60);
  return minutes === 1 ? "1 minuto" : `${minutes} minutos`;
}

export function formatRelative(value: string, now: number = Date.now()): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const diffSeconds = Math.round((date.getTime() - now) / 1000);
  const absolute = Math.abs(diffSeconds);
  if (absolute > 7 * 24 * 60 * 60) return formatDate(value);

  const relative = new Intl.RelativeTimeFormat("pt-BR", { numeric: "auto" });
  if (absolute < 60) return relative.format(diffSeconds, "second");
  if (absolute < 60 * 60) return relative.format(Math.round(diffSeconds / 60), "minute");
  if (absolute < 24 * 60 * 60) return relative.format(Math.round(diffSeconds / 3600), "hour");
  return relative.format(Math.round(diffSeconds / 86400), "day");
}

export function formatError(error: unknown): string {
  if (error instanceof TypeError) {
    return "Não foi possível conectar ao servidor. Verifique sua conexão e tente novamente.";
  }
  if (!(error instanceof ApiError)) {
    return "Não foi possível concluir a operação. Tente novamente.";
  }
  if (error.status >= 500 && error.code === "request_failed") {
    return "O servidor encontrou um erro ao processar a operação. Tente novamente em instantes.";
  }

  switch (error.code) {
    case "invalid_phone":
      return "Telefone inválido. Confira o país, o DDD e o número.";
    case "rate_limited": {
      const wait = error.retryAfterSeconds;
      if (wait === null || wait <= 0) {
        return "Muitas tentativas. Aguarde um instante e tente novamente.";
      }
      return `Muitas tentativas. Tente novamente em ${formatWait(wait)}.`;
    }
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
    case "refund_failed":
      return "O provedor não aceitou o reembolso. Nenhuma cobrança foi estornada; confira o extrato financeiro.";
    case "psp_unavailable":
      return "O provedor de pagamento está indisponível agora. Tente novamente em instantes.";
    case "role_not_allowed":
      return "Seu papel não permite gerenciar esse membro.";
    case "last_owner_required":
      return "A organização precisa de pelo menos um proprietário.";
    case "member_already_exists":
      return "Esse usuário já é membro da organização.";
    case "member_not_found":
      return "Membro não encontrado nesta organização.";
    case "user_not_found":
      return "Usuário não encontrado.";
    case "user_not_active":
      return "Esse usuário não está ativo.";
    case "organization_not_found":
      return "Organização não encontrada ou fora do seu acesso.";
    case "venue_not_found":
      return "Estabelecimento não encontrado ou fora do seu acesso.";
    case "space_not_found":
      return "Quadra não encontrada ou fora do seu acesso.";
    case "booking_not_found":
      return "Reserva não encontrada ou fora do seu acesso.";
    case "release_not_found":
      return "A reserva ainda não tem valor liberável.";
    case "dispute_not_found":
      return "Contestação não encontrada ou fora do seu acesso.";
    case "dispute_already_open":
      return "Já existe uma contestação em análise para esta reserva.";
    case "invalid_input":
      return "Algum campo está inválido. Revise os valores destacados e tente novamente.";
    case "invalid_postal_code":
      return "CEP inválido. Informe os oito dígitos.";
    case "postal_code_not_found":
      return "Não encontramos esse CEP. Confira os dígitos ou informe o endereço manualmente.";
    case "geocoding_timeout":
      return "O serviço de CEP demorou para responder. Tente novamente em instantes.";
    case "geocoding_provider_error":
      return "O serviço de CEP está indisponível agora. Tente novamente ou informe as coordenadas manualmente.";
    case "validation_error": {
      const details = error.fields.map((field) => field.message).filter(Boolean);
      if (details.length > 0) {
        return `${error.message || "Dados inválidos"}: ${details.join(" ")}`;
      }
      return error.message || "Dados inválidos. Revise os campos e tente novamente.";
    }
    case "invalid_time_range":
      return "O período informado é inválido. Verifique se o fim é depois do início.";
    case "price_above_band":
      return "O preço ultrapassa o teto da faixa máxima permitida. Reduza o valor da janela.";
    case "space_name_exists":
      return "Já existe uma quadra com esse nome neste estabelecimento.";
    case "availability_conflict":
      return "Já existe uma janela de agenda conflitante nesse dia e horário.";
    case "availability_overlap":
      return "A janela se sobrepõe a outra já cadastrada.";
    case "blackout_overlap":
      return "O bloqueio se sobrepõe a outro período já bloqueado.";
    case "business_hour_conflict":
      return "Já existe um expediente conflitante para esse dia.";
    case "invalid_photo":
      return "A imagem não foi aceita. Use JPEG, PNG ou WebP de até 5 MB e dimensões entre 200 e 4000 px.";
    case "photo_too_large":
      return "A foto ultrapassa o limite de 5 MB.";
    case "photo_storage_unavailable":
      return "O armazenamento de fotos está indisponível no momento. Tente novamente em instantes.";
    case "review_not_allowed":
      return "Somente proprietário ou administrador pode revisar fotos.";
    case "moderator_required":
      return "Sua conta não tem permissão de moderação.";
    case "notification_not_found":
      return "Notificação não encontrada ou já pertence a outro operador.";
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
