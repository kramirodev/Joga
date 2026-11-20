import assert from 'node:assert/strict';
import test from 'node:test';

import { classifyRefreshFailure } from './refreshPolicy.ts';

test('401 invalid_refresh_token e refresh_reuse_detected deslogam', () => {
  assert.equal(classifyRefreshFailure(401, 'invalid_refresh_token'), 'expired');
  assert.equal(classifyRefreshFailure(401, 'refresh_reuse_detected'), 'expired');
});

test('account_suspended só vem do corpo explícito do servidor', () => {
  assert.equal(classifyRefreshFailure(401, 'account_suspended'), 'suspended');
  assert.equal(classifyRefreshFailure(403, 'account_suspended'), 'suspended');
  // Qualquer outro 401/403 é sessão inválida, não suspensão.
  assert.equal(classifyRefreshFailure(401, 'invalid_token'), 'expired');
  assert.equal(classifyRefreshFailure(403, 'ranked_restricted'), 'expired');
});

test('rede, timeout, 5xx e 429 não deslogam nem suspendem', () => {
  assert.equal(classifyRefreshFailure(0, 'network_unavailable'), 'unavailable');
  assert.equal(classifyRefreshFailure(0, 'request_timeout'), 'unavailable');
  assert.equal(classifyRefreshFailure(500, null), 'unavailable');
  assert.equal(classifyRefreshFailure(503, 'server_error'), 'unavailable');
  assert.equal(classifyRefreshFailure(429, 'rate_limited'), 'unavailable');
});

test('nunca classifica falha desconhecida como suspensão', () => {
  assert.equal(classifyRefreshFailure(418, 'teapot'), 'expired');
  assert.equal(classifyRefreshFailure(0, null), 'unavailable');
});
