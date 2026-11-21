import assert from 'node:assert/strict';
import test from 'node:test';

import {
  chatRowFromMessage,
  displayClanTag,
  isDuplicateReport,
  isReportableMessage,
  joinPolicyLabel,
  memberDisplayName,
  mergeChatRows,
  myRoleLabel,
  normalizeTagInput,
  sortMembers,
  tagIsValid,
  tagPayload,
} from './clanSocial.ts';

test('tag é maiúscula, sem # e só aceita A-Z0-9', () => {
  assert.equal(normalizeTagInput(' q9 '), 'Q9');
  assert.equal(normalizeTagInput('#volei-6'), 'VOLEI6');
  assert.equal(normalizeTagInput('abcdefghij'), 'ABCDEFG');
  assert.equal(tagPayload('q9'), '#Q9');
});

test('tag válida tem 2 a 7 caracteres', () => {
  assert.equal(tagIsValid('A'), false);
  assert.equal(tagIsValid('Q9'), true);
  assert.equal(tagIsValid('ABCDEFG'), true);
  assert.equal(tagIsValid('ABCDEFGH'), false);
});

test('exibição prefixa # apenas quando falta', () => {
  assert.equal(displayClanTag('Q9'), '#Q9');
  assert.equal(displayClanTag('#Q9'), '#Q9');
  assert.equal(displayClanTag('  '), '#—');
  assert.equal(displayClanTag(null), '#—');
});

test('approval não é achatado em closed', () => {
  assert.equal(joinPolicyLabel('open'), 'Aberto');
  assert.equal(joinPolicyLabel('approval'), 'Aprovação');
  assert.equal(joinPolicyLabel('closed'), 'Fechado');
});

test('papel do servidor vira Dono/Oficial/Membro', () => {
  assert.equal(myRoleLabel('owner'), 'Dono');
  assert.equal(myRoleLabel('admin'), 'Oficial');
  assert.equal(myRoleLabel('member'), 'Membro');
  assert.equal(myRoleLabel(null), 'Membro');
});

test('membro sempre tem nome legível, inclusive vazio e a própria linha', () => {
  assert.equal(memberDisplayName({ user_id: '1', display_name: 'Ana' }), 'Ana');
  assert.equal(
    memberDisplayName(
      { user_id: '1', display_name: '' },
      { selfUserId: '1', selfProfileName: 'Bia' },
    ),
    'Bia',
  );
  assert.equal(
    memberDisplayName(
      { user_id: '1', display_name: '   ' },
      { selfUserId: '1', selfProfileName: 'Bia' },
    ),
    'Bia',
  );
  assert.equal(
    memberDisplayName({ user_id: '1', display_name: null }, { selfUserId: '1' }),
    'Jogador',
  );
  assert.equal(memberDisplayName({ user_id: '2', display_name: '' }), 'Jogador');
  assert.equal(
    memberDisplayName(
      { user_id: '2', display_name: null },
      { selfUserId: '1', selfProfileName: 'Bia' },
    ),
    'Jogador',
  );
});

test('só mensagem confirmada é denunciável', () => {
  assert.equal(isReportableMessage({ serverId: 'srv-1', status: 'sent' }), true);
  assert.equal(isReportableMessage({ serverId: null, status: 'sending' }), false);
  assert.equal(isReportableMessage({ serverId: null, status: 'failed' }), false);
});

test('409 e duplicata contam como já denunciada', () => {
  assert.equal(isDuplicateReport({ status: 409, code: 'reason_invalid' }), true);
  assert.equal(isDuplicateReport({ status: 201, code: 'already_reported' }), true);
  assert.equal(isDuplicateReport({ status: 201, code: 'duplicate_report' }), true);
  assert.equal(isDuplicateReport({ status: 500, code: 'server_error' }), false);
  assert.equal(isDuplicateReport({ status: 404, code: 'not_found' }), false);
});

test('membros são ordenados por dono, oficiais e nome', () => {
  const ordered = sortMembers([
    { user_id: '3', display_name: 'Bia', role: 'member' },
    { user_id: '1', display_name: 'Rafa', role: 'admin' },
    { user_id: '2', display_name: 'Ana', role: 'owner' },
  ]);
  assert.deepEqual(
    ordered.map((member) => member.user_id),
    ['2', '1', '3'],
  );
});

test('chat ordena antigas acima e deduplica o id do servidor', () => {
  const server = [
    {
      id: 'b',
      sender_id: 's',
      display_name: null,
      body: 'nova',
      hidden: false,
      created_at: '2026-01-01T12:01:00Z',
    },
    {
      id: 'a',
      sender_id: 's',
      display_name: null,
      body: 'antiga',
      hidden: false,
      created_at: '2026-01-01T12:00:00Z',
    },
  ];
  const local = [
    chatRowFromMessage(server[0]),
    {
      key: 'local-1',
      serverId: null,
      senderId: 's',
      displayName: null,
      body: 'enviando',
      createdAt: '2026-01-01T12:02:00Z',
      status: 'sending',
    },
  ];
  const rows = mergeChatRows(server, local);
  assert.deepEqual(
    rows.map((row) => row.body),
    ['antiga', 'nova', 'enviando'],
  );
  assert.equal(rows.filter((row) => row.body === 'nova').length, 1);
});
