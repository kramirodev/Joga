import assert from 'node:assert/strict';
import test from 'node:test';

import { isProfileSurface, PROFILE_SURFACE_IDS, queueMatchDestination } from './queueRouting.ts';

const matched = (lobbyId = 'lobby-1') => ({
  mode: 'casual',
  lobby: { id: lobbyId },
});

test('sem partida encontrada, nenhuma navegação', () => {
  assert.equal(queueMatchDestination('profile-me', null, null), null);
  assert.equal(queueMatchDestination('profile-me', undefined, null), null);
});

test('partida sem lobby preparado ainda não navega', () => {
  assert.equal(queueMatchDestination('profile-me', { mode: 'casual', lobby: null }, null), null);
});

test('fora das telas de perfil, a precedência global não interfere', () => {
  for (const screenId of ['home', 'friends', 'matches', 'queue', 'queue-search', 'lobby-found']) {
    assert.equal(queueMatchDestination(screenId, matched(), null), null, screenId);
  }
});

test('perfil próprio, público/olhinho e edição perdem para o match', () => {
  for (const screenId of ['profile-me', 'profile-other', 'profile-edit']) {
    assert.deepEqual(
      queueMatchDestination(screenId, matched(), null),
      { screen: 'lobby-found', params: { lobbyId: 'lobby-1', mode: 'casual' } },
      screenId,
    );
  }
});

test('todo id declarado como superfície de perfil é reconhecido', () => {
  for (const screenId of PROFILE_SURFACE_IDS) {
    assert.equal(isProfileSurface(screenId), true, screenId);
  }
  assert.equal(isProfileSurface('home'), false);
  assert.equal(isProfileSurface('lobby-detail'), false);
});

test('idempotente: o mesmo lobby navega uma única vez', () => {
  const first = queueMatchDestination('profile-me', matched(), null);
  assert.ok(first);
  assert.equal(queueMatchDestination('profile-me', matched(), first.params.lobbyId), null);
  // Mesmo com a tela de perfil remontada, o lobby já tratado não puxa de novo.
  assert.equal(queueMatchDestination('profile-other', matched(), first.params.lobbyId), null);
});

test('um lobby novo volta a ter precedência mesmo depois do anterior', () => {
  const first = queueMatchDestination('profile-me', matched('lobby-1'), null);
  assert.ok(first);
  assert.deepEqual(queueMatchDestination('profile-me', matched('lobby-2'), first.params.lobbyId), {
    screen: 'lobby-found',
    params: { lobbyId: 'lobby-2', mode: 'casual' },
  });
});
