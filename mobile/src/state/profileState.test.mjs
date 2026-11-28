import assert from 'node:assert/strict';
import test from 'node:test';

import {
  avatarTargetFor,
  canRequestFriendship,
  equippedBadgeNames,
  equippedBadges,
  friendSearchPrefill,
  normalizeProfileTag,
  profileClanName,
  profileTagForCard,
  profileTagLabel,
  publicCardFields,
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
  assert.equal(avatarTargetFor('me'), 'profile-edit');
  assert.equal(avatarTargetFor('edit'), 'identity-editor');
  assert.equal(avatarTargetFor('other'), null);
});

test('snapshot público sem card não inventa dados do cartão', () => {
  assert.deepEqual(publicCardFields(null), {
    tier: null,
    level: null,
    qualifier: null,
    seasonLabel: null,
    record: null,
    winstreak: null,
    badges: [],
    visual: null,
    themeId: null,
  });
  assert.deepEqual(
    publicCardFields({
      user_id: 'u1',
      display_name: 'Ana',
      tag: '#AB12',
      relation: 'none',
      clan: null,
    }),
    {
      tier: null,
      level: null,
      qualifier: null,
      seasonLabel: null,
      record: null,
      winstreak: null,
      badges: [],
      visual: null,
      themeId: null,
    },
  );
});

test('snapshot público mapeia o card e limita insígnias a três', () => {
  const fields = publicCardFields({
    user_id: 'u1',
    display_name: 'Ana',
    tag: '#AB12',
    relation: 'friend',
    clan: null,
    card: {
      theme_id: 'noite-quadra',
      visual: null,
      tier: 'Prata',
      level: 7,
      qualifier: 'DIVISÃO 2',
      season_label: 'T4 2026',
      record: 42,
      win_streak: 3,
      badges: [
        { code: 'a', name: 'Fundadora', kind: 'founder' },
        { code: 'b', name: 'Primeira vitória', kind: 'match' },
        { code: 'c', name: 'Clã', kind: 'clan' },
        { code: 'd', name: 'Extra', kind: 'other' },
      ],
    },
  });
  assert.deepEqual(fields, {
    tier: 'Prata',
    level: 7,
    qualifier: 'DIVISÃO 2',
    seasonLabel: 'T4 2026',
    record: 42,
    winstreak: 3,
    badges: ['Fundadora', 'Primeira vitória', 'Clã'],
    visual: null,
    themeId: 'noite-quadra',
  });
});

test('quadros do cartão usam só as insígnias equipadas, na ordem do slot', () => {
  const badges = [
    {
      badge_id: '1',
      code: 'a',
      name: 'Sem slot',
      kind: 'match',
      equipped_slot: null,
      awarded_at: '',
    },
    { badge_id: '2', code: 'b', name: 'Segunda', kind: 'match', equipped_slot: 2, awarded_at: '' },
    {
      badge_id: '3',
      code: 'c',
      name: 'Primeira',
      kind: 'founder',
      equipped_slot: 1,
      awarded_at: '',
    },
    { badge_id: '4', code: 'd', name: 'Terceira', kind: 'clan', equipped_slot: 3, awarded_at: '' },
    { badge_id: '5', code: 'e', name: 'Quarta', kind: 'other', equipped_slot: 4, awarded_at: '' },
  ];
  assert.deepEqual(equippedBadgeNames(badges), ['Primeira', 'Segunda', 'Terceira']);
  assert.deepEqual(
    equippedBadges(badges).map((badge) => badge.badge_id),
    ['3', '2', '4'],
  );
  assert.deepEqual(equippedBadgeNames(null), []);
});
