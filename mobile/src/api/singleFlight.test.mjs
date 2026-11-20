import assert from 'node:assert/strict';
import test from 'node:test';

import { createSingleFlight } from './singleFlight.ts';

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((ok, fail) => {
    resolve = ok;
    reject = fail;
  });
  return { promise, resolve, reject };
}

test('duas chamadas concorrentes com a mesma chave fazem um único POST', async () => {
  const gate = createSingleFlight();
  const blocker = deferred();
  let calls = 0;
  const task = async () => {
    calls += 1;
    await blocker.promise;
    return 'access-token';
  };

  const first = gate.run('refresh-token-a', task);
  const second = gate.run('refresh-token-a', task);

  // A prova do single-flight: uma execução para duas chamadas.
  assert.equal(calls, 1);
  assert.equal(gate.size(), 1);

  blocker.resolve();
  assert.deepEqual(await Promise.all([first, second]), ['access-token', 'access-token']);
  assert.equal(calls, 1);
  assert.equal(gate.size(), 0);
});

test('erro é compartilhado e a chave é liberada para uma nova tentativa', async () => {
  const gate = createSingleFlight();
  const blocker = deferred();
  let calls = 0;
  const task = async () => {
    calls += 1;
    await blocker.promise;
    throw new Error('refresh_reuse_detected');
  };

  const first = gate.run('refresh-token-b', task);
  const second = gate.run('refresh-token-b', task);
  blocker.reject(new Error('refresh_reuse_detected'));

  await assert.rejects(first, /refresh_reuse_detected/);
  await assert.rejects(second, /refresh_reuse_detected/);
  assert.equal(calls, 1);

  // Depois da falha, a próxima tentativa roda de novo (sem cache de erro).
  const recovered = await gate.run('refresh-token-b', async () => {
    calls += 1;
    return 'novo-token';
  });
  assert.equal(recovered, 'novo-token');
  assert.equal(calls, 2);
});

test('chaves diferentes não compartilham a promessa', async () => {
  const gate = createSingleFlight();
  let calls = 0;
  const task = async () => {
    calls += 1;
    return calls;
  };
  const a = gate.run('sessao-1', task);
  const b = gate.run('sessao-2', task);
  assert.deepEqual(await Promise.all([a, b]), [1, 2]);
  assert.equal(calls, 2);
});

test('forget libera a chave sem cancelar a promessa em voo', async () => {
  const gate = createSingleFlight();
  const blocker = deferred();
  const running = gate.run('sessao-3', async () => {
    await blocker.promise;
    return 'ok';
  });
  gate.forget('sessao-3');
  assert.equal(gate.size(), 0);
  blocker.resolve();
  assert.equal(await running, 'ok');
});
