import type { ClanMyRequest, ClanMyRequestStatus } from '../api/types';

/**
 * Regras puras do fluxo de pedido de entrada em clã.
 *
 * A decisão de autorização continua no servidor. Aqui só traduzimos o estado
 * devolvido por ele (`my_request`, resposta do `join` e códigos de erro) em
 * ação de card, etapa da tela e texto curto — sem guardar "pendente" local.
 */

export type ClanCardAction = 'open' | 'pending' | 'resend' | 'join' | 'request' | 'closed' | 'full';

/**
 * Ação do card de descoberta, na ordem em que o servidor manda:
 * membro abre, pedido pendente bloqueia reenvio, vaga/política fecham a
 * entrada e, por último, o pedido anterior recusado/cancelado vira reenvio.
 */
export function clanCardAction(input: {
  is_member: boolean;
  my_request: Pick<ClanMyRequest, 'status'> | null | undefined;
  join_policy: string | null | undefined;
  full: boolean;
}): ClanCardAction {
  if (input.is_member) {
    return 'open';
  }
  if (input.my_request?.status === 'pending') {
    return 'pending';
  }
  if (input.full) {
    return 'full';
  }
  if (input.join_policy === 'closed') {
    return 'closed';
  }
  if (input.join_policy === 'open') {
    return 'join';
  }
  if (input.my_request?.status === 'rejected' || input.my_request?.status === 'cancelled') {
    return 'resend';
  }
  return 'request';
}

export function clanCardActionLabel(action: ClanCardAction, busy = false): string {
  switch (action) {
    case 'open':
      return 'Abrir';
    case 'pending':
      return 'Pendente';
    case 'resend':
      return 'Solicitar de novo';
    case 'join':
      return busy ? 'Entrando…' : 'Entrar';
    case 'request':
      return 'Solicitar';
    case 'closed':
      return 'Fechado';
    case 'full':
      return 'Cheio';
  }
}

/**
 * Texto auxiliar do card. Cancelar não é recusar: cada estado do pedido
 * anterior tem sua própria copy, mesmo que a ação continue `resend`.
 */
export function clanCardHint(input: {
  action: ClanCardAction;
  myRequestStatus: ClanMyRequestStatus | null | undefined;
  vacancies: number;
}): string {
  switch (input.action) {
    case 'pending':
      return 'Aguardando aprovação do clã';
    case 'resend':
      return input.myRequestStatus === 'cancelled'
        ? 'Você cancelou seu pedido anterior.'
        : 'Seu pedido anterior não foi aprovado.';
    case 'open':
      return 'Você já participa deste clã';
    case 'full':
      return 'Sem vaga';
    case 'closed':
      return 'Não aceita entradas';
    case 'join':
    case 'request':
      return `${Math.max(0, input.vacancies)} vagas`;
  }
}

export type ClanJoinStep = 'form' | 'pending' | 'joined';

/**
 * Etapa da tela de entrada: a resposta vence o detalhe carregado, e ambos
 * vencem o formulário. `rejected`/`cancelled` voltam ao formulário para um
 * novo pedido, nunca a uma tela de "enviado".
 */
export function clanJoinState(
  myRequest: Pick<ClanMyRequest, 'status'> | null | undefined,
  response?:
    { status: string; request?: { status: ClanMyRequestStatus } | null } | null | undefined,
): ClanJoinStep {
  if (response?.status === 'joined') {
    return 'joined';
  }
  const status = response?.request?.status;
  if (status === 'pending') {
    return 'pending';
  }
  if (status === 'approved') {
    return 'joined';
  }
  if (myRequest?.status === 'pending') {
    return 'pending';
  }
  return 'form';
}

const CLAN_REQUEST_ERROR_COPY: Record<string, string> = {
  admin_required: 'Só o Dono e os Oficiais podem decidir pedidos.',
  owner_required: 'Só o dono do clã pode fazer isso.',
  not_a_member: 'Você não participa deste clã.',
  already_member: 'Você já é membro deste clã.',
  already_in_clan: 'Você já está em outro clã. Saia do atual antes de entrar em outro.',
  already_requested: 'Você já tem um pedido pendente para este clã.',
  request_not_pending: 'Este pedido já foi decidido.',
  already_invited: 'Este convite já foi enviado.',
  invite_not_found: 'Este convite não está mais disponível.',
  invite_expired: 'Este convite expirou.',
  not_friends: 'Só é possível convidar amigos.',
  blocked: 'Não é possível convidar esta pessoa.',
  cannot_invite_self: 'Você não pode convidar a si mesmo.',
  clan_full: 'Clã cheio. Volte quando abrir uma vaga.',
  clan_cooldown: 'Você saiu de um clã há menos de 7 dias. Tente novamente mais tarde.',
  clan_closed: 'Este clã não aceita novas entradas.',
  not_found: 'Clã não encontrado. Atualize a lista.',
  rate_limited: 'Muitas ações em pouco tempo. Aguarde um pouco e tente de novo.',
  network_unavailable: 'Sem conexão. Verifique sua internet e tente de novo.',
  request_timeout: 'A conexão demorou demais. Tente de novo.',
};

const CLAN_REQUEST_ERROR_FALLBACK = 'Não foi possível agora. Tente de novo.';

export function clanRequestErrorCopy(code: string | null | undefined): string {
  if (!code) {
    return CLAN_REQUEST_ERROR_FALLBACK;
  }
  return CLAN_REQUEST_ERROR_COPY[code] ?? CLAN_REQUEST_ERROR_FALLBACK;
}

export function clanRequestStatusLabel(status: string | null | undefined): string {
  if (status === 'pending') {
    return 'Pendente';
  }
  if (status === 'approved') {
    return 'Aprovado';
  }
  if (status === 'rejected') {
    return 'Recusado';
  }
  if (status === 'cancelled') {
    return 'Cancelado';
  }
  return 'Sem status';
}
