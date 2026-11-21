import assert from 'node:assert/strict';
import test from 'node:test';

import { createStackEntry, sameParams, shouldPush } from './navigationStack.ts';

test('cada entrada da pilha recebe uid próprio, mesmo com id/params iguais', () => {
  const first = createStackEntry('queue-search');
  const second = createStackEntry('queue-search');
  assert.notEqual(first.uid, second.uid);
  assert.equal(first.id, second.id);
  assert.deepEqual(first.params, second.params);
});

test('go para o mesmo topo não empilha', () => {
  const top = createStackEntry('queue-search', {});
  assert.equal(shouldPush(top, 'queue-search', {}), false);
  assert.equal(shouldPush(top, 'queue-search', { from: 'queue' }), true);
  assert.equal(shouldPush(top, 'queue', {}), true);
});

test('comparação de params não depende da ordem das chaves', () => {
  assert.equal(sameParams({ a: '1', b: 2 }, { b: 2, a: '1' }), true);
  assert.equal(sameParams({ a: '1' }, { a: '2' }), false);
  assert.equal(sameParams({ a: '1' }, { a: '1', b: null }), false);
  assert.equal(sameParams({}, {}), true);
});

test('pilha vazia sempre permite a primeira entrada', () => {
  assert.equal(shouldPush(null, 'home'), true);
  assert.equal(shouldPush(undefined, 'home'), true);
});
