import assert from 'node:assert/strict';
import test from 'node:test';

import {
  classifyRefreshFailure,
  isExplicitSessionRevocation,
  sessionRecoveryDecision,
  shouldRetryRefresh,
} from './refreshPolicy.ts';

test('refresh_retry_required é transitório: retry uma vez e mantém a sessão', () => {
  assert.equal(classifyRefreshFailure(401, 'refresh_retry_required'), 'retry');
  assert.equal(classifyRefreshFailure(403, 'refresh_retry_required'), 'retry');
  assert.equal(shouldRetryRefresh(401, 'refresh_retry_required'), true);
  assert.equal(shouldRetryRefresh(403, 'refresh_retry_required'), true);
  assert.equal(shouldRetryRefresh(401, 'invalid_refresh_token'), false);
  assert.equal(shouldRetryRefresh(500, null), false);
  assert.equal(sessionRecoveryDecision(401, 'refresh_retry_required'), 'keep');
});

test('só revogação explícita do refresh desloga e limpa os tokens', () => {
  assert.equal(classifyRefreshFailure(401, 'invalid_refresh_token'), 'expired');
  assert.equal(classifyRefreshFailure(401, 'refresh_reuse_detected'), 'expired');
  assert.equal(sessionRecoveryDecision(401, 'invalid_refresh_token'), 'clear');
  assert.equal(sessionRecoveryDecision(401, 'refresh_reuse_detected'), 'clear');
});

test('account_suspended só vem do corpo explícito e nunca limpa a sessão', () => {
  assert.equal(classifyRefreshFailure(401, 'account_suspended'), 'suspended');
  assert.equal(classifyRefreshFailure(403, 'account_suspended'), 'suspended');
  // Tem precedência até sobre 5xx: a suspensão é decisão de produto.
  assert.equal(classifyRefreshFailure(503, 'account_suspended'), 'suspended');
  assert.equal(sessionRecoveryDecision(401, 'account_suspended'), 'keep');
});

test('rede, timeout, 5xx e 429 mantêm a sessão', () => {
  assert.equal(classifyRefreshFailure(0, 'network_unavailable'), 'unavailable');
  assert.equal(classifyRefreshFailure(0, 'request_timeout'), 'unavailable');
  assert.equal(classifyRefreshFailure(500, null), 'unavailable');
  assert.equal(classifyRefreshFailure(503, 'server_error'), 'unavailable');
  assert.equal(classifyRefreshFailure(429, 'rate_limited'), 'unavailable');
  for (const [status, code] of [
    [0, 'network_unavailable'],
    [0, 'request_timeout'],
    [500, null],
    [503, 'server_error'],
    [429, 'rate_limited'],
  ]) {
    assert.equal(sessionRecoveryDecision(status, code), 'keep');
  }
});

test('4xx sem código de revogação não prova sessão encerrada', () => {
  assert.equal(classifyRefreshFailure(401, 'invalid_token'), 'expired');
  assert.equal(classifyRefreshFailure(401, null), 'unavailable');
  assert.equal(classifyRefreshFailure(401, 'unexpected_code'), 'unavailable');
  assert.equal(classifyRefreshFailure(403, 'ranked_restricted'), 'unavailable');
  assert.equal(classifyRefreshFailure(418, 'teapot'), 'unavailable');
  assert.equal(sessionRecoveryDecision(401, null), 'keep');
});

test('lista de revogação explícita é fechada', () => {
  assert.equal(isExplicitSessionRevocation('invalid_refresh_token'), true);
  assert.equal(isExplicitSessionRevocation('refresh_reuse_detected'), true);
  assert.equal(isExplicitSessionRevocation('invalid_token'), true);
  assert.equal(isExplicitSessionRevocation('refresh_retry_required'), false);
  assert.equal(isExplicitSessionRevocation('account_suspended'), false);
  assert.equal(isExplicitSessionRevocation(null), false);
  assert.equal(isExplicitSessionRevocation(''), false);
});
