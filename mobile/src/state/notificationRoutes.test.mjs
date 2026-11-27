import assert from 'node:assert/strict';
import test from 'node:test';

import { notificationRouteFor } from './notificationRoutes.ts';

test('sem data não há rota', () => {
  assert.equal(notificationRouteFor(null), null);
  assert.equal(notificationRouteFor(undefined), null);
  assert.equal(notificationRouteFor('kind'), null);
});

test('kind conhecido leva à tela correspondente', () => {
  assert.deepEqual(notificationRouteFor({ kind: 'friend_accepted' }), {
    screen: 'friends',
    params: {},
  });
  assert.deepEqual(notificationRouteFor({ kind: 'friend_request_received' }), {
    screen: 'friends',
    params: {},
  });
  assert.deepEqual(notificationRouteFor({ kind: 'clan_invite', clan_id: 'c1' }), {
    screen: 'clan',
    params: { clanId: 'c1' },
  });
  assert.deepEqual(notificationRouteFor({ kind: 'clan_join_request', clan_id: 'c2' }), {
    screen: 'clan',
    params: { clanId: 'c2' },
  });
  assert.deepEqual(notificationRouteFor({ kind: 'substitute', match_id: 'm1' }), {
    screen: 'match-detail',
    params: { matchId: 'm1' },
  });
  assert.deepEqual(notificationRouteFor({ kind: 'match_created', match_id: 'm2' }), {
    screen: 'match-detail',
    params: { matchId: 'm2' },
  });
  assert.deepEqual(notificationRouteFor({ kind: 'booking_confirmed' }), {
    screen: 'booking-history',
    params: {},
  });
});

test('kind desconhecido cai na central e não inventa tela', () => {
  assert.deepEqual(notificationRouteFor({ kind: 'novidade_do_backend' }), {
    screen: 'notifications',
    params: {},
  });
  assert.deepEqual(notificationRouteFor({}), { screen: 'notifications', params: {} });
});

test('type serve de fallback quando kind não vem', () => {
  assert.deepEqual(notificationRouteFor({ type: 'LOBBY_INVITE', lobbyId: 'l1' }), {
    screen: 'lobby-detail',
    params: { lobbyId: 'l1' },
  });
});

test('ids vazios ou de outro tipo são ignorados', () => {
  assert.deepEqual(notificationRouteFor({ kind: 'lobby', lobby_id: '  ' }), {
    screen: 'lobby-detail',
    params: {},
  });
  assert.deepEqual(notificationRouteFor({ kind: 'match', matchId: 42 }), {
    screen: 'match-detail',
    params: {},
  });
});

test('lobby prefere lobbyId a matchId no mesmo payload', () => {
  assert.deepEqual(
    notificationRouteFor({
      kind: 'lobby',
      lobby_id: 'l1',
      match_id: 'm1',
    }),
    { screen: 'lobby-detail', params: { lobbyId: 'l1' } },
  );
});
