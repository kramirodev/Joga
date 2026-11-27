import assert from 'node:assert/strict';
import test from 'node:test';

import {
  avatarTargetFor,
  canRequestFriendship,
  friendSearchPrefill,
  normalizeProfileTag,
  profileClanName,
  profileTagForCard,
  profileTagLabel,
  publicProfileStatus,
  publicProfileStatusLabel,
} from './profileState.ts';

test('tag canônica perde #, espaços e caixa sem virar tag fake', () => {
  assert.equal(normalizeProfileTag('#9f55a2c1'), '9F55A2C1');
  assert.equal(normalizeProfileTag(' ##ab 12 '), 'AB12');
  assert.equal(normalizeProfileTag(''), '');
  assert.equal(normalizeProfileTag(null), '');
});

test('tag de exibição e do cartão não duplicam #', () => {
  assert.equal(profileTagLabel('#9F55A2C1'), '#9F55A2C1');
  assert.equal(profileTagLabel('9F55A2C1'), '#9F55A2C1');
  assert.equal(profileTagLabel(''), '—');
  assert.equal(profileTagForCard('#9F55A2C1'), '9F55A2C1');
  assert.equal(profileTagForCard(undefined), '—');
});

test('clã só vira "Sem clã" depois da carga', () => {
  assert.equal(profileClanName('Quadra 9', false), 'Quadra 9');
  assert.equal(profileClanName('  Quadra 9  ', true), 'Quadra 9');
  assert.equal(profileClanName(null, false), '—');
  assert.equal(profileClanName(null, true), 'Sem clã');
  assert.equal(profileClanName('', true), 'Sem clã');
});

test('perfil público esconde amizade para si, amigo e pedido pendente', () => {
  assert.equal(publicProfileStatus(true, 'friend'), 'self');
  assert.equal(publicProfileStatus(false, 'friend'), 'friend');
  assert.equal(publicProfileStatus(false, 'incoming_request'), 'incoming_request');
  assert.equal(publicProfileStatus(false, 'outgoing_request'), 'outgoing_request');
  assert.equal(publicProfileStatus(false, 'none'), 'public');
  assert.equal(publicProfileStatus(false, null), 'public');

  assert.equal(canRequestFriendship(true, 'none'), false);
  assert.equal(canRequestFriendship(false, 'friend'), false);
  assert.equal(canRequestFriendship(false, 'incoming_request'), false);
  assert.equal(canRequestFriendship(false, 'outgoing_request'), false);
  assert.equal(canRequestFriendship(false, 'none'), true);

  assert.equal(publicProfileStatusLabel('self'), 'VOCÊ');
  assert.equal(publicProfileStatusLabel('friend'), 'AMIGO');
  assert.equal(publicProfileStatusLabel('incoming_request'), 'PEDIDO RECEBIDO');
  assert.equal(publicProfileStatusLabel('outgoing_request'), 'PEDIDO ENVIADO');
  assert.equal(publicProfileStatusLabel('public'), 'PERFIL PÚBLICO');
});

test('busca recebe nome e tag reais, sem preencher lixo', () => {
  assert.deepEqual(friendSearchPrefill('  Ana  ', '#ab12'), { name: 'Ana', tag: 'AB12' });
  assert.deepEqual(friendSearchPrefill(null, null), { name: '', tag: '' });
});

test('toque no avatar leva ao destino certo por tela', () => {
  assert.equal(avatarTargetFor('me'), 'profile-other');
  assert.equal(avatarTargetFor('edit'), 'identity-editor');
  assert.equal(avatarTargetFor('other'), null);
});
