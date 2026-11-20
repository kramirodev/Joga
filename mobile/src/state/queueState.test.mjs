import assert from 'node:assert/strict';
import test from 'node:test';

import {
  applyNetworkFailure,
  applyReplaceResult,
  buildSelection,
  cancelOutcome,
  formatLabelFromCatalog,
  isExpired,
  isNetworkFailure,
  isStaleRevision,
  lobbyIdFromQueue,
  nextPollDelay,
  oldestCreatedAt,
  queueFailureMessage,
  reconcileEntries,
  selectionError,
  selectionFromEntries,
  selectionProduct,
  selectionProductCount,
  snapshotCoversSelection,
  snapshotFromEntries,
  summarizeEntries,
} from './queueState.ts';

const NOW = Date.parse('2026-11-20T12:00:00Z');

function entry(overrides = {}) {
  return {
    id: 'entry-1',
    format_id: 'format-1',
    mode: 'casual',
    court_preference: 'ANY',
    level: 'intermediate',
    status: 'waiting',
    radius_km: 8,
    created_at: '2026-11-20T11:58:00Z',
    expires_at: '2026-11-20T13:00:00Z',
    lobby: null,
    ...overrides,
  };
}

function lobby(id = 'lobby-1') {
  return {
    id,
    mode: 'casual',
    court_preference: 'ANY',
    scheduled_start_at: '2026-11-20T20:00:00Z',
    scheduled_end_at: '2026-11-20T21:00:00Z',
    duration_minutes: 60,
  };
}

test('1 formato × 1 modo → uma entrada', () => {
  const selection = buildSelection(['f1'], ['casual']);
  assert.deepEqual(selection, { formats: ['f1'], modes: ['casual'] });
  assert.equal(selectionProductCount(selection), 1);
  assert.deepEqual(selectionProduct(selection), [{ formatId: 'f1', mode: 'casual' }]);
});

test('1 formato × 2 modos → duas entradas', () => {
  const selection = buildSelection(['f1'], ['casual', 'ranked']);
  assert.equal(selectionProductCount(selection), 2);
  assert.deepEqual(
    selectionProduct(selection).map((item) => item.mode),
    ['casual', 'ranked'],
  );
});

test('2 formatos × 2 modos → quatro combinações sem duplicata', () => {
  const selection = buildSelection(['f1', 'f2', 'f1'], ['casual', 'ranked', 'casual']);
  assert.deepEqual(selection, { formats: ['f1', 'f2'], modes: ['casual', 'ranked'] });
  const product = selectionProduct(selection);
  assert.equal(product.length, 4);
  assert.equal(new Set(product.map((item) => `${item.formatId}:${item.mode}`)).size, 4);
});

test('arrays vazios, modo inválido e duplicidade são validados antes da rede', () => {
  assert.match(selectionError({ formats: [], modes: ['casual'] }) ?? '', /esporte/);
  assert.match(selectionError({ formats: ['f1'], modes: [] }) ?? '', /modo/);
  assert.equal(selectionError({ formats: ['f1'], modes: ['casual'] }), null);
  assert.deepEqual(buildSelection([], ['casual', 'invalid', 'casual']), {
    formats: [],
    modes: ['casual'],
  });
});

test('GET reconcilia entries e usa entry legado só como compatibilidade', () => {
  const entries = [
    entry({ id: 'a', format_id: 'f1' }),
    entry({ id: 'b', format_id: 'f1', mode: 'ranked' }),
    entry({ id: 'c', format_id: 'f2' }),
  ];
  const snapshot = reconcileEntries({ entries, entry: entries[2] }, NOW);
  assert.equal(snapshot.entries.length, 3);
  assert.equal(snapshot.matched, null);
  assert.equal(snapshot.duplicates, 0);
  assert.deepEqual(
    snapshot.entries.map((item) => item.id),
    ['a', 'b', 'c'],
  );
});

test('entry matched fora de entries vira matched, sem duplicar', () => {
  const waiting = [entry({ id: 'a' }), entry({ id: 'b', mode: 'ranked' })];
  const matched = {
    ...entry({ id: 'm', status: 'matched', lobby: lobby('lobby-9') }),
  };
  const snapshot = reconcileEntries({ entries: waiting, entry: matched }, NOW);
  assert.equal(snapshot.entries.length, 2);
  assert.equal(snapshot.matched?.id, 'm');
  assert.equal(snapshot.matched?.lobby?.id, 'lobby-9');
});

test('PUT substitui a seleção: não soma entradas antigas', () => {
  const previous = snapshotFromEntries([
    entry({ id: 'old-1', format_id: 'f1' }),
    entry({ id: 'old-2', format_id: 'f1', mode: 'ranked' }),
    entry({ id: 'old-3', format_id: 'f2' }),
    entry({ id: 'old-4', format_id: 'f2', mode: 'ranked' }),
  ]);
  const replaced = applyReplaceResult(
    previous,
    {
      entries: [entry({ id: 'new-1', format_id: 'f2' })],
      entry: entry({ id: 'new-1', format_id: 'f2' }),
    },
    NOW,
  );
  assert.deepEqual(
    replaced.entries.map((item) => item.id),
    ['new-1'],
  );
});

test('timeout no PUT + GET com seleção nova adota a nova', () => {
  const previous = snapshotFromEntries([entry({ id: 'old', format_id: 'f1' })]);
  const selection = buildSelection(['f1', 'f2'], ['casual']);
  const reloaded = {
    entries: [entry({ id: 'new-1', format_id: 'f1' }), entry({ id: 'new-2', format_id: 'f2' })],
    entry: null,
  };
  const outcome = applyNetworkFailure(previous, reloaded, NOW);
  assert.equal(outcome.reconciled, true);
  assert.equal(outcome.snapshot.entries.length, 2);
  assert.equal(snapshotCoversSelection(outcome.snapshot, selection), true);
});

test('timeout no PUT + GET com seleção antiga mantém a antiga', () => {
  const previous = snapshotFromEntries([entry({ id: 'old', format_id: 'f1' })]);
  const selection = buildSelection(['f1', 'f2'], ['casual']);
  const reloaded = {
    entries: [entry({ id: 'old', format_id: 'f1' })],
    entry: entry({ id: 'old', format_id: 'f1' }),
  };
  const outcome = applyNetworkFailure(previous, reloaded, NOW);
  assert.equal(outcome.snapshot.entries.length, 1);
  assert.equal(outcome.snapshot.entries[0].id, 'old');
  assert.equal(snapshotCoversSelection(outcome.snapshot, selection), false);
});

test('GET também falhou: mantém a última lista confirmada', () => {
  const previous = snapshotFromEntries([entry({ id: 'old' })]);
  const outcome = applyNetworkFailure(previous, null, NOW);
  assert.equal(outcome.reconciled, false);
  assert.equal(outcome.snapshot, previous);
});

test('DELETE 204 e 404 not_queued são idempotentes; 500/rede mantêm', () => {
  assert.equal(cancelOutcome(204), 'cleared');
  assert.equal(cancelOutcome(404), 'cleared');
  assert.equal(cancelOutcome(500), 'keep');
  assert.equal(cancelOutcome(0), 'keep');
});

test('falha de rede exige releitura; 4xx não', () => {
  assert.equal(isNetworkFailure(0, 'network_unavailable'), true);
  assert.equal(isNetworkFailure(0, 'request_timeout'), true);
  assert.equal(isNetworkFailure(403, 'ranked_restricted'), false);
  assert.equal(isNetworkFailure(400, 'invalid_format'), false);
  assert.equal(isNetworkFailure(409, 'queue_conflict'), false);
});

test('403 ranked_restricted exibe erro e preserva a lista anterior', () => {
  const previous = snapshotFromEntries([entry({ id: 'old' })]);
  const outcome = applyNetworkFailure(previous, null, NOW);
  assert.equal(outcome.snapshot.entries.length, 1);
  const message = queueFailureMessage('ranked_restricted');
  assert.match(message, /Ranqueada indisponível/);
  assert.doesNotMatch(message, /ranked_restricted/);
});

test('entrada matched + três waiting: distingue sem escolher vencedor', () => {
  const matched = entry({ id: 'm', status: 'matched', lobby: lobby() });
  const snapshot = reconcileEntries(
    {
      entries: [entry({ id: 'a' }), entry({ id: 'b' }), entry({ id: 'c' })],
      entry: matched,
    },
    NOW,
  );
  assert.equal(snapshot.entries.length, 3);
  assert.equal(snapshot.matched?.id, 'm');
  assert.equal(
    snapshot.entries.some((item) => item.id === 'm'),
    false,
  );
});

test('empate: servidor devolve uma matched e outra waiting; UI reflete', () => {
  const snapshot = reconcileEntries(
    {
      entries: [entry({ id: 'other', created_at: '2026-11-20T11:59:00Z' })],
      entry: entry({ id: 'winner', status: 'matched', lobby: lobby('lobby-w') }),
    },
    NOW,
  );
  assert.equal(snapshot.matched?.id, 'winner');
  assert.equal(snapshot.entries[0].id, 'other');
});

test('matched[] do contrato 0057 é lido sem depender do entry legado', () => {
  const winner = entry({ id: 'winner', status: 'matched', lobby: lobby('lobby-m') });
  const snapshot = reconcileEntries(
    {
      entries: [entry({ id: 'waiting-1' })],
      matched: [winner],
      entry: null,
    },
    NOW,
  );
  assert.equal(snapshot.entries.length, 1);
  assert.equal(snapshot.matched?.id, 'winner');
  assert.equal(snapshot.matched?.lobby?.id, 'lobby-m');
});

test('matched[] + entry legado duplicado não duplica nem troca o vencedor', () => {
  const winner = entry({ id: 'winner', status: 'matched', lobby: lobby('lobby-m') });
  const snapshot = reconcileEntries(
    {
      entries: [winner, entry({ id: 'waiting-1' })],
      matched: [winner],
      entry: winner,
    },
    NOW,
  );
  assert.deepEqual(
    snapshot.entries.map((item) => item.id),
    ['waiting-1'],
  );
  assert.equal(snapshot.matched?.id, 'winner');
  assert.equal(snapshot.duplicates, 0);
});

test('vários matched: mostra o primeiro (mais recente), sem escolher localmente', () => {
  const newest = entry({ id: 'newest', status: 'matched', lobby: lobby('lobby-new') });
  const older = entry({ id: 'older', status: 'matched', lobby: lobby('lobby-old') });
  const snapshot = reconcileEntries({ entries: [], matched: [newest, older], entry: null }, NOW);
  assert.equal(snapshot.matched?.id, 'newest');
  assert.equal(snapshot.entries.length, 0);
});

test('expires_at vencido é removido da lista', () => {
  const expired = entry({ id: 'expired', expires_at: '2026-11-20T11:59:00Z' });
  assert.equal(isExpired(expired, NOW), true);
  const snapshot = reconcileEntries({ entries: [expired, entry({ id: 'ok' })], entry: null }, NOW);
  assert.deepEqual(
    snapshot.entries.map((item) => item.id),
    ['ok'],
  );
  assert.deepEqual(
    snapshot.expired.map((item) => item.id),
    ['expired'],
  );
});

test('poll antigo após cancelar é ignorado pela geração', () => {
  assert.equal(isStaleRevision(3, 4), true);
  assert.equal(isStaleRevision(4, 4), false);
  const empty = snapshotFromEntries([]);
  const stale = reconcileEntries({ entries: [entry({ id: 'a' })], entry: null }, NOW);
  assert.equal(stale.entries.length, 1);
  // O provider descarta `stale` porque a geração da resposta não é a atual;
  // o estado confirmado continua vazio.
  assert.equal(empty.entries.length, 0);
});

test('resumo, mais antiga, modos e seleção derivada do servidor', () => {
  const entries = [
    entry({ id: 'a', format_id: 'f1', created_at: '2026-11-20T11:50:00Z' }),
    entry({ id: 'b', format_id: 'f1', mode: 'ranked', created_at: '2026-11-20T11:55:00Z' }),
    entry({ id: 'c', format_id: 'f2', created_at: '2026-11-20T11:57:00Z' }),
  ];
  assert.equal(oldestCreatedAt(entries), '2026-11-20T11:50:00Z');
  const summary = summarizeEntries(entries);
  assert.equal(summary.count, 3);
  assert.deepEqual(summary.modes, [
    { mode: 'casual', count: 2 },
    { mode: 'ranked', count: 1 },
  ]);
  assert.deepEqual(selectionFromEntries(entries), {
    formats: ['f1', 'f2'],
    modes: ['casual', 'ranked'],
  });
});

test('formato desconhecido usa rótulo fallback sem quebrar', () => {
  assert.equal(formatLabelFromCatalog([], 'missing'), 'Formato indisponível');
  assert.equal(
    formatLabelFromCatalog(
      [
        {
          id: 's1',
          slug: 'futebol',
          name: 'Futebol',
          formats: [
            {
              id: 'f1',
              slug: 'futebol-5',
              name: 'Futebol 5x5',
              team_size: 5,
              total_participants: 10,
              play_minutes: 50,
              break_minutes: 10,
              duration_minutes: 60,
              version: 1,
            },
          ],
        },
      ],
      'f1',
    ),
    'Futebol 5x5',
  );
});

test('lobby prefere a entrada encontrada e backoff não passa de 30 s', () => {
  const matched = entry({ id: 'm', status: 'matched', lobby: lobby('lobby-matched') });
  assert.equal(
    lobbyIdFromQueue([entry({ id: 'a', lobby: lobby('lobby-a') })], matched),
    'lobby-matched',
  );
  assert.equal(nextPollDelay(0), 5_000);
  assert.equal(nextPollDelay(1), 5_000);
  assert.equal(nextPollDelay(2), 10_000);
  assert.equal(nextPollDelay(3), 20_000);
  assert.equal(nextPollDelay(4), 30_000);
  assert.equal(nextPollDelay(9), 30_000);
});
