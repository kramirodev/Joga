import assert from 'node:assert/strict';
import test from 'node:test';

import { retryTokenAfterRefresh } from './tokenRetry.ts';

test('token atual já mudou: repete com o token da sessão, sem novo refresh', () => {
  assert.equal(
    retryTokenAfterRefresh('token-antigo', 'token-novo', 'token-do-refresh'),
    'token-novo',
  );
});

test('token atual é o mesmo enviado: usa o token devolvido pelo refresh', () => {
  assert.equal(
    retryTokenAfterRefresh('token-atual', 'token-atual', 'token-renovado'),
    'token-renovado',
  );
});

test('sem token atual: usa o token devolvido pelo refresh', () => {
  assert.equal(retryTokenAfterRefresh('token-antigo', null, 'token-renovado'), 'token-renovado');
  assert.equal(
    retryTokenAfterRefresh('token-antigo', undefined, 'token-renovado'),
    'token-renovado',
  );
});
