/**
 * Regras puras da busca e da amizade.
 *
 * Nada aqui decide autorização: o servidor continua sendo a fonte da verdade.
 * Estas funções só traduzem entrada da tela em consulta e códigos de erro em
 * texto curto, para que a UI não invente mensagens nem mostre código cru.
 */

export type FriendAction = 'add' | 'sent' | 'accept' | 'friend';

/**
 * Consulta aceita pelo servidor: `NOME#TAG`, `#TAG` ou `NOME`.
 * Nome e tag são preenchidos de forma independente; espaços das pontas somem e
 * a consulta vai em maiúsculas (o nome canônico também é maiúsculo).
 */
export function composePlayerQuery(name: string, tag: string): string {
  const cleanName = name.trim().toUpperCase();
  const cleanTag = tag.replace(/#/g, '').replace(/\s+/g, '').trim().toUpperCase();
  if (cleanName && cleanTag) {
    return `${cleanName}#${cleanTag}`;
  }
  if (cleanTag) {
    return `#${cleanTag}`;
  }
  return cleanName;
}

/** Ação da linha de resultado, derivada só da relação devolvida pelo servidor. */
export function friendActionFor(relation: string | null | undefined): FriendAction {
  switch (relation) {
    case 'outgoing_request':
      return 'sent';
    case 'incoming_request':
      return 'accept';
    case 'friend':
      return 'friend';
    default:
      return 'add';
  }
}

const FRIEND_ERROR_COPY: Record<string, string> = {
  already_friends: 'Vocês já são amigos.',
  friend_request_exists: 'O pedido já foi enviado.',
  incoming_friend_request: 'Essa pessoa já enviou um pedido para você. Aceite o pedido recebido.',
  blocked_relationship: 'Não é possível enviar pedido para este jogador.',
  user_not_found: 'Este jogador não está mais disponível.',
  cannot_target_self: 'Você não pode adicionar você mesmo.',
  friendship_not_found: 'Este pedido não está mais disponível.',
  rate_limited: 'Muitas ações em pouco tempo. Aguarde um pouco e tente de novo.',
  invalid_search_query: 'Busque com pelo menos 3 caracteres.',
  network_unavailable: 'Sem conexão. Verifique sua internet e tente de novo.',
  request_timeout: 'A busca demorou demais. Tente de novo.',
  request_failed: 'Não foi possível agora. Tente de novo.',
};

const FRIEND_ERROR_FALLBACK = 'Não foi possível agora. Tente de novo.';

export function friendErrorCopy(code: string | null | undefined): string {
  if (!code) {
    return FRIEND_ERROR_FALLBACK;
  }
  return FRIEND_ERROR_COPY[code] ?? FRIEND_ERROR_FALLBACK;
}

/** Identidade pública curta: nome canônico com a tag quando ela existe. */
export function playerHandle(
  name: string | null | undefined,
  tag: string | null | undefined,
): string {
  const display = name?.trim() || 'Jogador';
  const cleanTag = (tag ?? '').trim().replace(/^#+/, '').toUpperCase();
  return cleanTag ? `${display}#${cleanTag}` : display;
}
