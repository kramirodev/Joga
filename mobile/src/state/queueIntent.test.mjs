import assert from 'node:assert/strict';
import test from 'node:test';

import {
  consumePendingQueueIntent,
  peekPendingQueueIntent,
  setPendingQueueIntent,
} from './queueIntent.ts';

const intent = {
  mode: 'casual',
  formatId: 'futebol-5x5',
  courtPreference: 'ANY',
};

test('intenção guardada é visível sem ser consumida', () => {
  setPendingQueueIntent(intent);
  assert.deepEqual(peekPendingQueueIntent(), intent);
  assert.deepEqual(peekPendingQueueIntent(), intent);
  assert.deepEqual(consumePendingQueueIntent(), intent);
});

test('consumir a intenção uma vez impede enqueue duplicado', () => {
  setPendingQueueIntent(intent);
  assert.deepEqual(consumePendingQueueIntent(), intent);
  assert.equal(consumePendingQueueIntent(), null);
  assert.equal(peekPendingQueueIntent(), null);
});

test('nova intenção substitui a anterior ainda pendente', () => {
  setPendingQueueIntent(intent);
  setPendingQueueIntent({ ...intent, mode: 'ranked' });
  assert.equal(consumePendingQueueIntent()?.mode, 'ranked');
  assert.equal(peekPendingQueueIntent(), null);
});
