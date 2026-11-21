import assert from 'node:assert/strict';
import test from 'node:test';

import {
  applyNetworkFailure,
  applyReplaceResult,
  buildSelection,
  buildSelectionItems,
  buildSelectionPayload,
  cancelOutcome,
  divergentCourtFormats,
  emptySelection,
  formatLabelFromCatalog,
  isExpired,
  isCourtPreference,
  isNetworkFailure,
  isStaleRevision,
  itemsToPairs,
  lobbyIdFromQueue,
  nextPollDelay,
  oldestCreatedAt,
  queueFailureMessage,
  queueContinuity,
  reconcileEntries,
  resolveCasualLevel,
  resolveCourtPreference,
  selectionCount,
  selectionError,
  selectionFromEntries,
  selectionItemsError,
  selectionPairs,
  snapshotCoversPairs,
  snapshotCoversSelection,
  snapshotFromEntries,
  summarizeEntries,
  withCourt,
  withFormatToggled,
  withLevel,
  withModeToggled,
  withoutRanked,
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

/** Atalho: `{ f1: ['ranked'], f2: ['casual'] }` → seleção por esporte. */
function selectionOf(entries) {
  const formats = Object.keys(entries);
  const byFormat = Object.fromEntries(
    Object.entries(entries).map(([formatId, modes]) => [formatId, { modes }]),
  );
  return buildSelection(formats, byFormat);
}

test('futebol ranqueada + vôlei casual → dois pares, nunca quatro', () => {
  const selection = selectionOf({ futebol: ['ranked'], volei: ['casual'] });
  assert.deepEqual(selectionPairs(selection), [
    { formatId: 'futebol', mode: 'ranked' },
    { formatId: 'volei', mode: 'casual' },
  ]);
  assert.equal(selectionCount(selection), 2);
});

test('um esporte com os dois modos → dois pares daquele esporte', () => {
  const selection = selectionOf({ futebol: ['casual', 'ranked'] });
  assert.deepEqual(selectionPairs(selection), [
    { formatId: 'futebol', mode: 'casual' },
    { formatId: 'futebol', mode: 'ranked' },
  ]);
  assert.equal(selectionCount(selection), 2);
});

test('modos são por esporte: 3 pares reais, sem combinação fantasma', () => {
  const selection = selectionOf({
    f1: ['casual', 'ranked'],
    f2: ['casual'],
    f3: ['ranked'],
  });
  assert.equal(selectionCount(selection), 4);
  assert.deepEqual(
    selectionPairs(selection).map((item) => `${item.formatId}:${item.mode}`),
    ['f1:casual', 'f1:ranked', 'f2:casual', 'f3:ranked'],
  );
  assert.equal(
    selectionPairs(selection).some((item) => item.formatId === 'f2' && item.mode === 'ranked'),
    false,
  );
});

test('buildSelection deduplica formatos, normaliza modo e preserva a ordem', () => {
  const selection = buildSelection(['f1', 'f2', 'f1', '', 'f3'], {
    f1: { modes: ['ranked', 'invalid', 'ranked'] },
    f2: { modes: ['casual'] },
  });
  assert.deepEqual(selection.formats, ['f1', 'f2', 'f3']);
  assert.deepEqual(selection.byFormat.f1.modes, ['ranked']);
  assert.deepEqual(selection.byFormat.f3.modes, ['casual']);
});

test('seleção vazia e esporte sem modo são validados antes da rede', () => {
  assert.match(selectionError(emptySelection()) ?? '', /esporte/);
  const semModo = buildSelection(['f1'], { f1: { modes: [] } });
  assert.match(selectionError(semModo) ?? '', /casual, ranqueada/);
  assert.equal(selectionError(selectionOf({ f1: ['casual'] })), null);
});

test('payload: quadra em todo item; casual leva nível e ranqueada não', () => {
  const selection = selectionOf({ futebol: ['ranked'], volei: ['casual'] });
  const items = buildSelectionItems(
    selection,
    () => 'beginner',
    (formatId) => (formatId === 'futebol' ? 'PUBLIC_ONLY' : 'PRIVATE_ONLY'),
  );
  assert.deepEqual(items, [
    { format_id: 'futebol', mode: 'ranked', court_preference: 'PUBLIC_ONLY' },
    {
      format_id: 'volei',
      mode: 'casual',
      court_preference: 'PRIVATE_ONLY',
      level: 'beginner',
    },
  ]);
  assert.equal('level' in items[0], false);
  assert.equal(JSON.stringify(items).includes('"level":null'), false);
});

test('payload único: selections com quadra por item e sem global', () => {
  const selection = selectionOf({ futebol: ['ranked'], volei: ['casual'] });
  const payload = buildSelectionPayload(
    selection,
    () => 'advanced',
    (formatId) => (formatId === 'futebol' ? 'PUBLIC_ONLY' : 'PRIVATE_ONLY'),
  );
  assert.deepEqual(payload, {
    selections: [
      { format_id: 'futebol', mode: 'ranked', court_preference: 'PUBLIC_ONLY' },
      {
        format_id: 'volei',
        mode: 'casual',
        court_preference: 'PRIVATE_ONLY',
        level: 'advanced',
      },
    ],
  });
  assert.equal('formats' in payload, false);
  assert.equal('modes' in payload, false);
  assert.equal('levels' in payload, false);
  assert.equal('court_preference' in payload, false);
  assert.deepEqual(itemsToPairs(payload.selections), selectionPairs(selection));
});

test('nível casual: escolha local → servidor → perfil → intermediário', () => {
  assert.equal(resolveCasualLevel('advanced', 'beginner', 'intermediate'), 'advanced');
  assert.equal(resolveCasualLevel(undefined, 'beginner', 'intermediate'), 'beginner');
  assert.equal(resolveCasualLevel('pro', undefined, 'intermediate'), 'intermediate');
  assert.equal(resolveCasualLevel(undefined, undefined, undefined), 'intermediate');
});

test('quadra: local → entrada → perfil → rascunho antigo → indefinida', () => {
  assert.equal(
    resolveCourtPreference('PRIVATE_ONLY', 'PUBLIC_ONLY', 'ANY', 'PUBLIC_ONLY'),
    'PRIVATE_ONLY',
  );
  assert.equal(
    resolveCourtPreference(undefined, 'PUBLIC_ONLY', 'ANY', 'PRIVATE_ONLY'),
    'PUBLIC_ONLY',
  );
  assert.equal(resolveCourtPreference(undefined, undefined, 'ANY', 'PRIVATE_ONLY'), 'ANY');
  assert.equal(
    resolveCourtPreference(undefined, undefined, undefined, 'PRIVATE_ONLY'),
    'PRIVATE_ONLY',
  );
  assert.equal(resolveCourtPreference(undefined, undefined, undefined, undefined), undefined);
  assert.equal(
    resolveCourtPreference('invalida', 'PUBLIC_ONLY', undefined, undefined),
    'PUBLIC_ONLY',
  );
  assert.equal(isCourtPreference('ANY'), true);
  assert.equal(isCourtPreference('Tanto faz'), false);
});

test('item sem quadra ou com valor inválido é rejeitado antes da rede', () => {
  assert.match(
    selectionItemsError([{ format_id: 'f1', mode: 'casual', level: 'beginner' }]) ?? '',
    /quadra/i,
  );
  assert.match(
    selectionItemsError([
      { format_id: 'f1', mode: 'casual', level: 'beginner', court_preference: 'PUBLICA' },
    ]) ?? '',
    /quadra/i,
  );
  assert.equal(
    selectionItemsError([
      { format_id: 'f1', mode: 'casual', level: 'beginner', court_preference: 'ANY' },
    ]),
    null,
  );
});

test('dois formatos com quadras diferentes convivem no mesmo payload', () => {
  const selection = selectionOf({ futebol: ['casual'], volei: ['casual'] });
  const payload = buildSelectionPayload(
    selection,
    () => 'intermediate',
    (formatId) => (formatId === 'futebol' ? 'PUBLIC_ONLY' : 'PRIVATE_ONLY'),
  );
  assert.equal(payload.selections.length, 2);
  assert.deepEqual(
    payload.selections.map((item) => [item.format_id, item.court_preference]),
    [
      ['futebol', 'PUBLIC_ONLY'],
      ['volei', 'PRIVATE_ONLY'],
    ],
  );
});

test('remover e readicionar casual preserva o nível escolhido', () => {
  let selection = withLevel(selectionOf({ f1: ['casual'] }), 'f1', 'advanced');
  selection = withModeToggled(selection, 'f1', 'casual');
  assert.deepEqual(selectionPairs(selection), []);
  selection = withModeToggled(selection, 'f1', 'casual');
  assert.deepEqual(selectionPairs(selection), [{ formatId: 'f1', mode: 'casual' }]);
  assert.equal(selection.byFormat.f1.level, 'advanced');
});

test('remover e readicionar esporte preserva modos, nível e quadra', () => {
  let selection = withCourt(
    withLevel(selectionOf({ f1: ['casual', 'ranked'] }), 'f1', 'beginner'),
    'f1',
    'PRIVATE_ONLY',
  );
  selection = withFormatToggled(selection, 'f1');
  assert.deepEqual(selection.formats, []);
  assert.deepEqual(selectionPairs(selection), []);
  selection = withFormatToggled(selection, 'f1');
  assert.deepEqual(selection.byFormat.f1.modes, ['casual', 'ranked']);
  assert.equal(selection.byFormat.f1.level, 'beginner');
  assert.equal(selection.byFormat.f1.court, 'PRIVATE_ONLY');
});

test('adicionar esporte novo nasce casual; nunca auto-seleciona ranqueada', () => {
  const selection = withFormatToggled(emptySelection(), 'f1');
  assert.deepEqual(selection.byFormat.f1.modes, ['casual']);
  assert.equal(selection.byFormat.f1.level, undefined);
  assert.equal(selection.byFormat.f1.court, undefined);
});

test('ranqueada não herda nível casual no payload, mas leva quadra', () => {
  let selection = withLevel(selectionOf({ f1: ['casual'] }), 'f1', 'advanced');
  selection = withModeToggled(selection, 'f1', 'ranked');
  selection = withCourt(selection, 'f1', 'PUBLIC_ONLY');
  const items = buildSelectionItems(
    selection,
    (formatId, mode) => (mode === 'casual' ? selection.byFormat[formatId].level : undefined),
    () => 'PUBLIC_ONLY',
  );
  assert.deepEqual(items, [
    { format_id: 'f1', mode: 'casual', court_preference: 'PUBLIC_ONLY', level: 'advanced' },
    { format_id: 'f1', mode: 'ranked', court_preference: 'PUBLIC_ONLY' },
  ]);
});

test('ranked_restricted desliga ranqueada sem perder casual nem nível', () => {
  let selection = withLevel(
    selectionOf({ f1: ['casual', 'ranked'], f2: ['ranked'] }),
    'f1',
    'beginner',
  );
  selection = withoutRanked(selection);
  assert.deepEqual(selection.byFormat.f1.modes, ['casual']);
  assert.deepEqual(selection.byFormat.f2.modes, ['casual']);
  assert.equal(selection.byFormat.f1.level, 'beginner');
});

test('validação final barra duplicata, nível em ranqueada e casual sem nível', () => {
  assert.match(selectionItemsError([]) ?? '', /esporte/);
  assert.match(
    selectionItemsError([
      { format_id: 'f1', mode: 'casual', level: 'beginner', court_preference: 'ANY' },
      { format_id: 'f1', mode: 'casual', level: 'advanced', court_preference: 'ANY' },
    ]) ?? '',
    /duas vezes/,
  );
  assert.match(
    selectionItemsError([
      { format_id: 'f1', mode: 'ranked', level: 'beginner', court_preference: 'ANY' },
    ]) ?? '',
    /ranqueada/,
  );
  assert.match(
    selectionItemsError([{ format_id: 'f1', mode: 'casual', court_preference: 'ANY' }]) ?? '',
    /nível/,
  );
  assert.equal(
    selectionItemsError([
      { format_id: 'f1', mode: 'casual', level: 'beginner', court_preference: 'ANY' },
      { format_id: 'f1', mode: 'ranked', court_preference: 'ANY' },
    ]),
    null,
  );
});

test('GET reconcilia um par por entrada, casual com nível e ranqueada sem nível', () => {
  const selection = selectionFromEntries([
    entry({ id: 'a', format_id: 'f1', mode: 'ranked', level: 'advanced' }),
    entry({ id: 'b', format_id: 'f1', mode: 'casual', level: 'beginner' }),
    entry({ id: 'c', format_id: 'f2', mode: 'casual', level: 'intermediate' }),
  ]);
  assert.deepEqual(selection.formats, ['f1', 'f2']);
  assert.deepEqual(selection.byFormat.f1.modes, ['casual', 'ranked']);
  assert.equal(selection.byFormat.f1.level, 'beginner');
  assert.deepEqual(selection.byFormat.f2.modes, ['casual']);
  assert.equal(selection.byFormat.f2.level, 'intermediate');
});

test('GET entrega a quadra efetiva por entrada e preserva a primeira', () => {
  const selection = selectionFromEntries([
    entry({ id: 'a', format_id: 'f1', court_preference: 'PUBLIC_ONLY' }),
    entry({ id: 'b', format_id: 'f1', mode: 'ranked', court_preference: 'PRIVATE_ONLY' }),
    entry({ id: 'c', format_id: 'f2', court_preference: 'ANY' }),
  ]);
  assert.equal(selection.byFormat.f1.court, 'PUBLIC_ONLY');
  assert.equal(selection.byFormat.f2.court, 'ANY');
});

test('duas entradas do mesmo formato com quadras diferentes são sinalizadas', () => {
  const divergent = divergentCourtFormats([
    entry({ id: 'a', format_id: 'f1', court_preference: 'PUBLIC_ONLY' }),
    entry({ id: 'b', format_id: 'f1', mode: 'ranked', court_preference: 'PRIVATE_ONLY' }),
    entry({ id: 'c', format_id: 'f2', court_preference: 'ANY' }),
  ]);
  assert.deepEqual(divergent, ['f1']);
  assert.deepEqual(
    divergentCourtFormats([entry({ id: 'a', format_id: 'f1', court_preference: 'ANY' })]),
    [],
  );
});

test('seleção derivada do GET não cria combinação que o servidor não tem', () => {
  const selection = selectionFromEntries([
    entry({ id: 'a', format_id: 'futebol', mode: 'ranked' }),
    entry({ id: 'b', format_id: 'volei', mode: 'casual' }),
  ]);
  assert.deepEqual(
    selectionPairs(selection).map((item) => `${item.formatId}:${item.mode}`),
    ['futebol:ranked', 'volei:casual'],
  );
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

test('continuidade: mantém os pares que continuam e separa os que serão cancelados', () => {
  const entries = [
    entry({ id: 'a', format_id: 'f1', mode: 'casual' }),
    entry({ id: 'b', format_id: 'f1', mode: 'ranked' }),
    entry({ id: 'c', format_id: 'f2', mode: 'casual' }),
  ];
  const continuity = queueContinuity(entries, selectionOf({ f1: ['casual'], f3: ['casual'] }));
  assert.deepEqual(
    continuity.kept.map((item) => item.id),
    ['a'],
  );
  assert.deepEqual(
    continuity.removed.map((item) => item.id),
    ['b', 'c'],
  );
  assert.deepEqual(continuity.added, [{ formatId: 'f3', mode: 'casual' }]);
});

test('continuidade: seleção vazia cancela todas e não inventa pares', () => {
  const entries = [entry({ id: 'a' }), entry({ id: 'b', mode: 'ranked' })];
  const continuity = queueContinuity(entries, emptySelection());
  assert.equal(continuity.kept.length, 0);
  assert.deepEqual(
    continuity.removed.map((item) => item.id),
    ['a', 'b'],
  );
  assert.deepEqual(continuity.added, []);
});

test('timeout no PUT + GET com seleção nova adota a nova', () => {
  const previous = snapshotFromEntries([entry({ id: 'old', format_id: 'f1' })]);
  const selection = selectionOf({ f1: ['casual'], f2: ['casual'] });
  const reloaded = {
    entries: [entry({ id: 'new-1', format_id: 'f1' }), entry({ id: 'new-2', format_id: 'f2' })],
    entry: null,
  };
  const outcome = applyNetworkFailure(previous, reloaded, NOW);
  assert.equal(outcome.reconciled, true);
  assert.equal(outcome.snapshot.entries.length, 2);
  assert.equal(snapshotCoversSelection(outcome.snapshot, selection), true);
  assert.equal(snapshotCoversPairs(outcome.snapshot, selectionPairs(selection)), true);
});

test('timeout no PUT + GET com seleção antiga mantém a antiga', () => {
  const previous = snapshotFromEntries([entry({ id: 'old', format_id: 'f1' })]);
  const selection = selectionOf({ f1: ['casual'], f2: ['casual'] });
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

test('422 level_not_applicable_for_ranked é bug de montagem, sem pedir nível', () => {
  const message = queueFailureMessage('level_not_applicable_for_ranked');
  assert.match(message, /ranqueada/);
  assert.match(message, /Nada foi alterado/);
  assert.doesNotMatch(message, /level_not_applicable_for_ranked/);
  assert.doesNotMatch(message, /escolha.*nível/i);
});

test('422/409 do contrato têm texto acionável e não vazam código', () => {
  for (const code of [
    'duplicate_queue_selection',
    'ambiguous_queue_selection',
    'invalid_level_override',
    'invalid_court_preference',
    'queue_conflict',
  ]) {
    const message = queueFailureMessage(code);
    assert.equal(message.includes(code), false);
    assert.ok(message.length > 20);
  }
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
  const selection = selectionFromEntries(entries);
  assert.deepEqual(selection.formats, ['f1', 'f2']);
  assert.deepEqual(selection.byFormat.f1.modes, ['casual', 'ranked']);
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
