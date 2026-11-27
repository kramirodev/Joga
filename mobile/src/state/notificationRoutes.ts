/**
 * Mapeamento puro de `kind`/`data` de uma notificação para uma tela do app.
 *
 * Fica separado de `src/notifications.ts` para ser testável sem carregar os
 * módulos nativos do Expo. A navegação (side effect) continua no ponto único.
 */

export type NotificationRouteParams = Record<string, string>;

export type NotificationRoute = {
  screen: string;
  params: NotificationRouteParams;
};

/** `kind` enviado pelo backend -> tela do app. `notifications` é o padrão. */
const KIND_SCREENS: Record<string, string> = {
  friend: 'friends',
  friends: 'friends',
  friendship: 'friends',
  friend_request: 'friends',
  friend_request_received: 'friends',
  friend_accepted: 'friends',
  friend_declined: 'friends',
  friend_cancelled: 'friends',
  amizade: 'friends',
  clan: 'clan',
  clan_invite: 'clan',
  clan_request: 'clan',
  clan_join_request: 'clan',
  clan_invite_accepted: 'clan',
  clan_invite_declined: 'clan',
  cla: 'clan',
  clã: 'clan',
  lobby: 'lobby-detail',
  lobby_invite: 'lobby-detail',
  lobby_full: 'lobby-detail',
  lobby_canceled: 'lobby-detail',
  match: 'match-detail',
  match_created: 'match-detail',
  match_result: 'match-detail',
  match_dispute: 'match-detail',
  substitute: 'match-detail',
  booking: 'booking-history',
  booking_confirmed: 'booking-history',
  notification: 'notifications',
  system: 'notifications',
  test: 'notifications',
};

function text(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

/**
 * Traduz `data` da notificação em rota única do app.
 *
 * Sem `data` não há rota. `kind` desconhecido cai na central de notificações,
 * que é o destino seguro quando o backend adicionar um tipo novo.
 */
export function notificationRouteFor(data: unknown): NotificationRoute | null {
  if (!data || typeof data !== 'object') {
    return null;
  }
  const payload = data as Record<string, unknown>;
  const kind = (text(payload.kind) ?? text(payload.type) ?? '').toLowerCase();
  const screen = KIND_SCREENS[kind] ?? 'notifications';
  const params: NotificationRouteParams = {};

  if (screen === 'lobby-detail') {
    const lobbyId = text(payload.lobbyId) ?? text(payload.lobby_id);
    const matchId = text(payload.matchId) ?? text(payload.match_id);
    if (lobbyId) {
      params.lobbyId = lobbyId;
    } else if (matchId) {
      params.matchId = matchId;
    }
  } else if (screen === 'match-detail') {
    const matchId = text(payload.matchId) ?? text(payload.match_id);
    if (matchId) {
      params.matchId = matchId;
    }
  } else if (screen === 'clan') {
    const clanId = text(payload.clanId) ?? text(payload.clan_id);
    if (clanId) {
      params.clanId = clanId;
    }
  }

  return { screen, params };
}
