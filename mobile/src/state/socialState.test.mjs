import assert from 'node:assert/strict';
import test from 'node:test';

import {
  composePlayerQuery,
  friendActionFor,
  friendErrorCopy,
  playerHandle,
} from './socialState.ts';

test('consulta combina nome e tag, só a tag ou só o nome', () => {
  assert.equal(composePlayerQuery('ana', '#ab12'), 'ANA#AB12');
  assert.equal(composePlayerQuery('  Ana  ', 'ab12'), 'ANA#AB12');
  assert.equal(composePlayerQuery('', '#ab12'), '#AB12');
  assert.equal(composePlayerQuery('', 'ab12'), '#AB12');
  assert.equal(composePlayerQuery(' ana ', ''), 'ANA');
  assert.equal(composePlayerQuery('', ''), '');
});

test('tag é normalizada sem #, sem espaço e em maiúsculas', () => {
  assert.equal(composePlayerQuery('', ' #a b 1 '), '#AB1');
  assert.equal(composePlayerQuery('joao', '##ab12'), 'JOAO#AB12');
});

test('ação da linha deriva da relação do servidor', () => {
  assert.equal(friendActionFor('none'), 'add');
  assert.equal(friendActionFor('outgoing_request'), 'sent');
  assert.equal(friendActionFor('incoming_request'), 'accept');
  assert.equal(friendActionFor('friend'), 'friend');
  assert.equal(friendActionFor(null), 'add');
  assert.equal(friendActionFor('desconhecida'), 'add');
});

test('erros de amizade viram texto curto sem código cru', () => {
  assert.equal(friendErrorCopy('already_friends'), 'Vocês já são amigos.');
  assert.equal(friendErrorCopy('friend_request_exists'), 'O pedido já foi enviado.');
  assert.match(friendErrorCopy('incoming_friend_request'), /já enviou um pedido/);
  assert.match(friendErrorCopy('blocked_relationship'), /Não é possível/);
  assert.match(friendErrorCopy('rate_limited'), /Muitas ações/);
  assert.match(friendErrorCopy('user_not_found'), /não está mais disponível/);
  assert.equal(friendErrorCopy(''), 'Não foi possível agora. Tente de novo.');
  assert.equal(friendErrorCopy('codigo_novo'), 'Não foi possível agora. Tente de novo.');
  assert.doesNotMatch(friendErrorCopy('codigo_novo'), /codigo_novo/);
});

test('identidade exibe nome#tag sem duplicar #', () => {
  assert.equal(playerHandle('Ana', '#AB12'), 'Ana#AB12');
  assert.equal(playerHandle('Ana', 'AB12'), 'Ana#AB12');
  assert.equal(playerHandle(' Ana ', undefined), 'Ana');
  assert.equal(playerHandle(null, null), 'Jogador');
});
