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
  PENDING: "Repasse pendente",
  RELEASED: "Repassado",
  FAILED: "Falhou",
  REVERSED: "Revertido após reembolso",
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
  PAYMENT_CONFIRMED: "Pagamento confirmado — parte da quadra",
  PAYMENT_REFUNDED: "Reembolso — devolução",
  VENUE_RELEASE: "Repasse ao fornecedor",
};

const FISCAL_STATUS: Record<string, string> = {
  pending_manual: "Intenção registrada — sem emissão",
  issued: "Emitida",
  processing: "Em processamento",
  failed: "Falhou",
  cancelled: "Cancelada",
  disabled: "Documento desativado",
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

const USER_STATUS: Record<string, string> = {
  pending: "Pendente",
  active: "Ativo",
  suspended: "Suspenso",
  deleted: "Excluído",
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
  "admin.user.created": "Usuário criado pela administração",
  "admin.user.create": "Usuário criado pela administração",
  "admin.user.email_changed": "E-mail de usuário alterado",
  "admin.user.email_change": "E-mail de usuário alterado",
  "admin.user.email_change_notice": "Aviso de troca de e-mail",
  "admin.user.password_reset": "Senha de usuário redefinida",
  "admin.user.suspended": "Usuário suspenso",
  "admin.user.suspend": "Usuário suspenso",
  "admin.user.reactivated": "Usuário reativado",
  "admin.user.reactivate": "Usuário reativado",
  "admin.user.sessions_revoked": "Sessões de usuário revogadas",
  "admin.user.sessions_revoke": "Sessões de usuário revogadas",
  "admin.sport.created": "Esporte criado",
  "admin.sport.create": "Esporte criado",
  "admin.sport.updated": "Esporte atualizado",
  "admin.sport.update": "Esporte atualizado",
  "admin.sport.activated": "Esporte publicado",
  "admin.sport.activate": "Esporte publicado",
  "admin.sport.deactivated": "Esporte desativado",
  "admin.sport.deactivate": "Esporte desativado",
  "admin.pricing.band_tickets_updated": "Tabela de tickets atualizada",
  "admin.pricing.band_tickets_override": "Tabela de tickets ajustada",
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
  user: "Usuário",
  sport: "Esporte",
  pricing_band: "Faixa de preço",
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

export function fiscalStatusLabel(status: string): string {
  return FISCAL_STATUS[status] ?? status;
}

export function organizationStatusLabel(status: string): string {
  return ORGANIZATION_STATUS[status] ?? status;
}

export function payoutStatusLabel(status: string): string {
  return PAYOUT_STATUS[status] ?? status;
}

export function userStatusLabel(status: string): string {
  return USER_STATUS[status] ?? status;
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
    case "invalid_email":
      return "E-mail inválido. Confira o endereço e tente novamente.";
    case "email_domain_not_allowed":
      return "Não aceitamos esse domínio de e-mail. Use outro endereço.";
    case "invalid_credentials":
    case "invalid_email_login":
      return "E-mail ou senha inválidos.";
    case "invalid_current_password":
      return "A senha atual está incorreta.";
    case "invalid_password":
    case "weak_password":
      return "A senha não atende aos requisitos. Use de 10 a 128 caracteres.";
    case "password_too_short":
      return "A senha deve ter pelo menos 10 caracteres.";
    case "password_too_long":
      return "A senha deve ter no máximo 128 caracteres.";
    case "password_equals_email":
      return "A senha não pode ser igual ao e-mail.";
    case "email_already_registered":
    case "email_already_exists":
    case "email_conflict":
    case "duplicate_email":
      return "Esse e-mail já está vinculado a outra conta. Use outro endereço.";
    case "platform_admin_required":
    case "admin_required":
      return "Sua conta não tem permissão de administração da plataforma.";
    case "ticket_purchase_disabled":
      return "A compra de tickets está temporariamente indisponível. Tente novamente mais tarde.";
    case "pricing_invariant_violation":
    case "band_ticket_invariant_violation":
    case "ticket_floor_violation":
      return "A quantidade de tickets não cobre o valor da quadra e a taxa. Aumente k antes de salvar.";
    case "pricing_mode_required":
      return "Escolha explicitamente entre modo padrão e contingência para este formato.";
    case "invalid_pricing_mode":
      return "O modo de preço informado é inválido para este formato.";
    case "band_not_found":
      return "Faixa de preço não encontrada.";
    case "sport_slug_exists":
    case "sport_slug_conflict":
      return "Já existe uma modalidade com esse slug.";
    case "sport_not_found":
      return "Modalidade não encontrada.";
    case "sport_not_publishable":
      return "A modalidade precisa de formato ativo e preço configurado nas faixas para ser publicada.";
    case "pricing_not_configured":
      return "O preço ainda não está configurado nas seis faixas. Configure o preço antes de salvar ou publicar.";
    case "format_in_use":
      return "Esse formato já está em uso por reservas. Crie um novo formato para mudar o tamanho da equipe.";
    case "venue_not_publishable":
      return "A quadra pública precisa de pelo menos um espaço ativo com preço configurado para ser publicada.";
    case "geocoding_required":
      return "Informe o CEP ou as coordenadas da quadra antes de publicar.";
    case "geocoding_unavailable":
      return "O serviço de CEP está indisponível agora. Tente novamente ou informe as coordenadas manualmente.";
    case "invalid_space":
      return "Modalidade, formato ou preço do espaço inválido. Revise o espaço e tente novamente.";
    case "platform_organization_missing":
      return "A organização de quadras públicas não está configurada. Fale com o suporte.";
    case "invalid_sport_icon":
      return "Ícone inválido. Use uma chave ativa do catálogo visual, como icon-sport-futebol-5x5.";
    case "invalid_sport":
      return "Os dados da modalidade são inválidos. Revise os formatos e tente novamente.";
    case "invalid_slug":
      return "O slug deve usar apenas minúsculas, números e hífens.";
    case "band_tickets_not_configured":
      return "A faixa ainda não tem tickets configurados para esse formato.";
    case "cannot_suspend_self":
      return "Você não pode suspender a própria conta.";
    case "invalid_status_transition":
      return "Essa mudança de status não é permitida no estado atual da conta.";
    case "email_unchanged":
      return "O novo e-mail é igual ao atual. Informe outro endereço.";
    case "reason_required":
      return "Informe o motivo da ação administrativa.";
    case "invalid_user":
      return "Os dados do usuário são inválidos. Revise os campos e tente novamente.";
    case "email_unavailable":
      return "O envio de e-mail está indisponível agora. Tente novamente mais tarde.";
    case "signup_closed":
      return "O cadastro está fechado no momento. Entre com uma conta existente.";
    case "email_registration_disabled":
      return "O cadastro por e-mail está indisponível no momento.";
    case "email_auth_disabled":
      return "O acesso por e-mail está indisponível no momento. Tente novamente mais tarde.";
    case "phone_auth_disabled":
      return "O acesso por telefone está indisponível. Use o acesso por e-mail.";
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
    case "invalid_password_reset":
      return "A verificação da senha expirou. Solicite um novo código.";
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
    case "dispute_not_open":
      return "A contestação não está aberta para decisão.";
    case "release_not_contestable":
      return "Esta liberação não pode mais ser contestada.";
    case "dispute_window_expired":
      return "O prazo de 72 horas para contestar esta reserva terminou.";
    case "operator_not_authorized":
      return "Somente a equipe de revisão do JOGA pode decidir esta contestação.";
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
    case "refresh_retry_required":
      return "Renovando sessão…";
    case "account_suspended":
      return "Sua conta está suspensa. Fale com o suporte para mais informações.";
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
