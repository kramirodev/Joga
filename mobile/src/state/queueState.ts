import type {
  QueueCourtPreference,
  QueueEntry,
  QueueLevel,
  QueueMode,
  QueueSelectionItem,
  QueueSelectionPayload,
  QueueStateResponse,
  Sport,
} from '../api/types';

/**
 * Lógica pura da fila multi-entrada (ADR 0057). Nada aqui fala com React ou
 * rede: são funções testáveis por `node --test`.
 *
 * Regra central: a seleção local é uma lista explícita de pares
 * `(formato, modo)`, nunca um produto cartesiano. As entradas confirmadas vêm
 * sempre do servidor (`entries` + `entry` legado).
 */

export const QUEUE_MODES: readonly QueueMode[] = ['casual', 'ranked'];

export const QUEUE_LEVELS: readonly QueueLevel[] = ['beginner', 'intermediate', 'advanced'];

/** Ordem aprovada na fila (difere da ordem do editor de perfil). */
export const QUEUE_COURT_OPTIONS: readonly QueueCourtPreference[] = [
  'PUBLIC_ONLY',
  'PRIVATE_ONLY',
  'ANY',
];

export const DEFAULT_QUEUE_MODES: readonly QueueMode[] = ['casual'];

/** Escolha de um esporte: modos marcados, nível casual e quadra. */
export type SportQueueChoice = {
  modes: QueueMode[];
  /** Nível do casual; ausente = default do servidor/perfil. */
  level?: QueueLevel;
  /** Quadra escolhida no card; ausente = ainda resolvendo o default. */
  court?: QueueCourtPreference;
};

/**
 * Seleção local por esporte. `byFormat` preserva modos e nível de esportes
 * desmarcados no Passo 1, então remover e readicionar não perde a escolha.
 */
export type QueueSelection = {
  /** Formatos escolhidos, na ordem de escolha do usuário. */
  formats: string[];
  byFormat: Record<string, SportQueueChoice>;
};

/** Par explícito da fila. */
export type QueuePair = {
  formatId: string;
  mode: QueueMode;
};

export type QueueSnapshot = {
  /** Entradas `waiting` válidas, na ordem do servidor (mais recente primeiro). */
  entries: QueueEntry[];
  /** Entrada `matched` (campo legado `entry`), se houver. */
  matched: QueueEntry | null;
  /** Entradas `waiting` já vencidas; removidas da UI com aviso. */
  expired: QueueEntry[];
  /** Ids repetidos entre `entries` e `entry`, descartados. */
  duplicates: number;
};

export type QueueReloadOutcome = {
  snapshot: QueueSnapshot;
  reconciled: boolean;
};

export type QueueReplaceOutcome =
  | { ok: true; snapshot: QueueSnapshot; reconciled: boolean }
  | { ok: false; code: string; snapshot: QueueSnapshot; reconciled: boolean };

export type QueueCancelOutcome = {
  ok: boolean;
  cleared: boolean;
  code: string | null;
  snapshot: QueueSnapshot;
};

export type QueueSummary = {
  count: number;
  formats: { formatId: string; count: number }[];
  modes: { mode: QueueMode; count: number }[];
  oldestCreatedAt: string | null;
};

/**
 * O que a próxima confirmação preserva e o que cancela. Usado pela revisão do
 * fluxo linear antes do `PUT`: nada é removido da lista confirmada antes do 2xx.
 */
export type QueueContinuity = {
  /** Entradas confirmadas cujo par continua na seleção. */
  kept: QueueEntry[];
  /** Entradas confirmadas que serão canceladas ao confirmar. */
  removed: QueueEntry[];
  /** Pares da seleção que ainda não existem no servidor. */
  added: QueuePair[];
};

export function emptySnapshot(): QueueSnapshot {
  return { entries: [], matched: null, expired: [], duplicates: 0 };
}

export function emptySelection(): QueueSelection {
  return { formats: [], byFormat: {} };
}

function unique<T>(values: readonly T[]): T[] {
  return Array.from(new Set(values));
}

export function normalizeModes(modes: readonly string[]): QueueMode[] {
  const result: QueueMode[] = [];
  for (const mode of modes) {
    if ((mode === 'casual' || mode === 'ranked') && !result.includes(mode)) {
      result.push(mode);
    }
  }
  return result;
}

export function isQueueLevel(value: unknown): value is QueueLevel {
  return value === 'beginner' || value === 'intermediate' || value === 'advanced';
}

export function isCourtPreference(value: unknown): value is QueueCourtPreference {
  return value === 'PUBLIC_ONLY' || value === 'PRIVATE_ONLY' || value === 'ANY';
}

/**
 * Default da quadra de um formato (ADR 0067): escolha local da sessão → valor
 * efetivo da entrada ativa → perfil do formato → rascunho global antigo →
 * `ANY`. `ANY` é valor real, nunca ausência.
 */
export function resolveCourtPreference(
  local: unknown,
  entry: unknown,
  profile: unknown,
  legacyDraft?: unknown,
): QueueCourtPreference | undefined {
  if (isCourtPreference(local)) {
    return local;
  }
  if (isCourtPreference(entry)) {
    return entry;
  }
  if (isCourtPreference(profile)) {
    return profile;
  }
  if (isCourtPreference(legacyDraft)) {
    return legacyDraft;
  }
  return undefined;
}

export function levelLabel(level: QueueLevel): string {
  if (level === 'beginner') {
    return 'Iniciante';
  }
  return level === 'advanced' ? 'Avançado' : 'Intermediário';
}

export function modeLabel(mode: QueueMode): string {
  return mode === 'ranked' ? 'Ranqueada' : 'Casual';
}

/**
 * Escolha de um esporte. Sem modos explícitos o default é casual; um esporte
 * com `modes: []` é intencionalmente vazio (erro acionável no Passo 2).
 */
export function sportChoice(
  modes: readonly string[] = DEFAULT_QUEUE_MODES,
  level?: QueueLevel | null,
  court?: QueueCourtPreference | null,
): SportQueueChoice {
  const normalized = normalizeModes(modes);
  return {
    modes: QUEUE_MODES.filter((mode) => normalized.includes(mode)),
    ...(isQueueLevel(level) ? { level } : {}),
    ...(isCourtPreference(court) ? { court } : {}),
  };
}

/**
 * Materializa a seleção a partir da lista de formatos e das escolhas por
 * formato. Deduplica formatos e mantém a ordem escolhida; não cria par que o
 * usuário não marcou.
 */
export function buildSelection(
  formats: readonly string[],
  byFormat: Readonly<Record<string, SportQueueChoice | undefined>>,
): QueueSelection {
  const selected: string[] = [];
  const result: Record<string, SportQueueChoice> = {};
  for (const formatId of formats) {
    if (typeof formatId !== 'string' || formatId.length === 0 || selected.includes(formatId)) {
      continue;
    }
    selected.push(formatId);
    const choice = byFormat[formatId];
    result[formatId] = choice
      ? sportChoice(choice.modes, choice.level, choice.court)
      : sportChoice();
  }
  return { formats: selected, byFormat: result };
}

/** Pares reais da seleção, em ordem estável (formato escolhido, casual antes). */
export function selectionPairs(selection: QueueSelection): QueuePair[] {
  const pairs: QueuePair[] = [];
  for (const formatId of selection.formats) {
    const modes = normalizeModes(selection.byFormat[formatId]?.modes ?? DEFAULT_QUEUE_MODES);
    for (const mode of modes) {
      pairs.push({ formatId, mode });
    }
  }
  return pairs;
}

export function selectionCount(selection: QueueSelection): number {
  return selectionPairs(selection).length;
}

/** Validação local antes de chamar o servidor; devolve texto acionável. */
export function selectionError(selection: QueueSelection): string | null {
  if (selection.formats.length === 0) {
    return 'Escolha pelo menos um esporte para buscar partida.';
  }
  for (const formatId of selection.formats) {
    const modes = selection.byFormat[formatId]?.modes ?? [];
    if (modes.length === 0) {
      return 'Escolha casual, ranqueada ou ambos em cada esporte selecionado.';
    }
  }
  return null;
}

export function isFormatSelected(selection: QueueSelection, formatId: string): boolean {
  return selection.formats.includes(formatId);
}

/** Liga/desliga um esporte sem descartar modos e nível já escolhidos. */
export function withFormatToggled(selection: QueueSelection, formatId: string): QueueSelection {
  if (!formatId) {
    return selection;
  }
  if (selection.formats.includes(formatId)) {
    return { ...selection, formats: selection.formats.filter((id) => id !== formatId) };
  }
  const current = selection.byFormat[formatId];
  const choice =
    current && current.modes.length > 0
      ? sportChoice(current.modes, current.level, current.court)
      : sportChoice(DEFAULT_QUEUE_MODES, current?.level, current?.court);
  return {
    formats: [...selection.formats, formatId],
    byFormat: { ...selection.byFormat, [formatId]: choice },
  };
}

/** Liga/desliga um modo daquele esporte; o nível casual é preservado. */
export function withModeToggled(
  selection: QueueSelection,
  formatId: string,
  mode: QueueMode,
): QueueSelection {
  const current = selection.byFormat[formatId] ?? sportChoice();
  const modes = current.modes.includes(mode)
    ? current.modes.filter((value) => value !== mode)
    : [...current.modes, mode];
  return {
    ...selection,
    byFormat: {
      ...selection.byFormat,
      [formatId]: {
        ...current,
        modes: QUEUE_MODES.filter((value) => modes.includes(value)),
      },
    },
  };
}

/** Guarda o nível casual escolhido para aquele esporte (nunca em ranqueada). */
export function withLevel(
  selection: QueueSelection,
  formatId: string,
  level: QueueLevel,
): QueueSelection {
  const current = selection.byFormat[formatId] ?? sportChoice();
  return {
    ...selection,
    byFormat: { ...selection.byFormat, [formatId]: { ...current, level } },
  };
}

/** Escolhe a quadra daquele formato; modos e nível ficam intactos. */
export function withCourt(
  selection: QueueSelection,
  formatId: string,
  court: QueueCourtPreference,
): QueueSelection {
  const current = selection.byFormat[formatId] ?? sportChoice();
  return {
    ...selection,
    byFormat: { ...selection.byFormat, [formatId]: { ...current, court } },
  };
}

/**
 * Reação a `ranked_restricted`: desliga ranqueada em todos os esportes e
 * garante ao menos casual em cada um, sem perder o nível já escolhido.
 */
export function withoutRanked(selection: QueueSelection): QueueSelection {
  const byFormat: Record<string, SportQueueChoice> = { ...selection.byFormat };
  for (const formatId of selection.formats) {
    const current = byFormat[formatId] ?? sportChoice();
    const modes = QUEUE_MODES.filter((mode) => mode !== 'ranked' && current.modes.includes(mode));
    byFormat[formatId] = { ...current, modes: modes.length > 0 ? modes : sportChoice().modes };
  }
  return { ...selection, byFormat };
}

export function isExpired(entry: QueueEntry, now: number = Date.now()): boolean {
  const expiresAt = Date.parse(entry.expires_at);
  return Number.isFinite(expiresAt) && expiresAt <= now;
}

export function entryMode(entry: QueueEntry): QueueMode {
  return entry.mode === 'ranked' ? 'ranked' : 'casual';
}

/**
 * Combina `entries` (todas as `waiting`) com `matched` (partidas encontradas
 * com lobby agendado), sem duplicar por id. O campo legado `entry` só é usado
 * quando o servidor não devolve `matched` — ele pode repetir uma `waiting` ou a
 * entrada encontrada.
 */
export function reconcileEntries(
  response: QueueStateResponse | null | undefined,
  now: number = Date.now(),
): QueueSnapshot {
  const waiting = Array.isArray(response?.entries) ? response.entries : [];
  const matchedEntries = Array.isArray(response?.matched) ? response.matched : [];
  const latest = response?.entry ?? null;
  const seen = new Set<string>();
  const entries: QueueEntry[] = [];
  const expired: QueueEntry[] = [];
  let duplicates = 0;
  let matched: QueueEntry | null = null;

  const consider = (entry: QueueEntry | null | undefined, countDuplicate: boolean) => {
    if (!entry || typeof entry.id !== 'string') {
      return;
    }
    if (seen.has(entry.id)) {
      if (countDuplicate) {
        duplicates += 1;
      }
      return;
    }
    seen.add(entry.id);
    if (entry.status === 'matched') {
      matched = matched ?? entry;
      return;
    }
    if (entry.status !== 'waiting') {
      return;
    }
    if (isExpired(entry, now)) {
      expired.push(entry);
      return;
    }
    entries.push(entry);
  };

  for (const entry of waiting) {
    consider(entry, true);
  }
  // `matched` vem do mais recente para o mais antigo; a UI representa a
  // primeira partida encontrada e as demais continuam no histórico do servidor.
  for (const entry of matchedEntries) {
    consider(entry, false);
  }
  consider(latest, false);

  return { entries, matched, expired, duplicates };
}

export function snapshotFromEntries(
  entries: QueueEntry[],
  matched: QueueEntry | null = null,
): QueueSnapshot {
  return { entries, matched, expired: [], duplicates: 0 };
}

/** `PUT` substitui: o resultado nunca soma com a lista anterior. */
export function applyReplaceResult(
  _previous: QueueSnapshot,
  response: QueueStateResponse | null | undefined,
  now: number = Date.now(),
): QueueSnapshot {
  return reconcileEntries(response, now);
}

/**
 * Timeout/erro de rede no `PUT` pode ter commitado. A única fonte de verdade é
 * reler o `GET`; se a releitura também falhar, mantém a última lista confirmada.
 */
export function applyNetworkFailure(
  previous: QueueSnapshot,
  reloaded: QueueStateResponse | null | undefined,
  now: number = Date.now(),
): QueueReloadOutcome {
  if (!reloaded) {
    return { snapshot: previous, reconciled: false };
  }
  return { snapshot: reconcileEntries(reloaded, now), reconciled: true };
}

export function cancelOutcome(status: number): 'cleared' | 'keep' {
  return status === 204 || status === 404 ? 'cleared' : 'keep';
}

/** Falha sem resposta do servidor: o PUT pode ter commitado e exige releitura. */
export function isNetworkFailure(status: number, code: string | null | undefined): boolean {
  return status === 0 || code === 'network_unavailable' || code === 'request_timeout';
}

/**
 * Uma resposta de poll/GET iniciada antes de `PUT`/`DELETE` não pode repor o
 * estado. A geração é incrementada em toda mutação e comparada na aplicação.
 */
export function isStaleRevision(expected: number, current: number): boolean {
  return expected !== current;
}

function combinationKey(formatId: string, mode: QueueMode): string {
  return `${formatId}::${mode}`;
}

export function levelKey(formatId: string, mode: QueueMode): string {
  return combinationKey(formatId, mode);
}

/**
 * Default do nível casual: escolha local → nível da entrada confirmada no
 * servidor → nível do perfil esportivo → intermediário (mesmo default da tela
 * de esportes). Nunca é usado para ranqueada.
 */
export function resolveCasualLevel(
  chosen: string | null | undefined,
  serverLevel: string | null | undefined,
  profileLevel: string | null | undefined,
): QueueLevel {
  if (isQueueLevel(chosen)) {
    return chosen;
  }
  if (isQueueLevel(serverLevel)) {
    return serverLevel;
  }
  if (isQueueLevel(profileLevel)) {
    return profileLevel;
  }
  return 'intermediate';
}

/**
 * Itens do campo `selections` do `PUT`, na ordem dos pares. Casual recebe o
 * nível resolvido; ranqueada **não** recebe a chave `level` (nem `null`).
 */
export function buildSelectionItems(
  selection: QueueSelection,
  levelFor: (formatId: string, mode: QueueMode) => string | null | undefined,
  courtFor: (formatId: string) => QueueCourtPreference | undefined,
): QueueSelectionItem[] {
  return selectionPairs(selection).map(({ formatId, mode }) => {
    const court = courtFor(formatId);
    const base: QueueSelectionItem = {
      format_id: formatId,
      mode,
      ...(isCourtPreference(court) ? { court_preference: court } : {}),
    };
    if (mode === 'ranked') {
      return base;
    }
    const level = levelFor(formatId, mode);
    return {
      ...base,
      level: isQueueLevel(level) ? level : 'intermediate',
    };
  });
}

/**
 * Validação final do payload. Duplicata de par, `level` em ranqueada ou casual
 * sem nível válido são bugs de montagem: barramos antes da rede.
 */
export function selectionItemsError(items: readonly QueueSelectionItem[]): string | null {
  if (items.length === 0) {
    return 'Escolha pelo menos um esporte e um modo para buscar partida.';
  }
  const seen = new Set<string>();
  for (const item of items) {
    const key = combinationKey(item.format_id, item.mode);
    if (seen.has(key)) {
      return 'A mesma combinação de esporte e modo apareceu duas vezes. Revise a seleção.';
    }
    seen.add(key);
    if (item.mode === 'ranked' && item.level !== undefined) {
      return 'Não foi possível montar a busca ranqueada. Nada foi alterado; tente novamente.';
    }
    if (item.mode === 'casual' && !isQueueLevel(item.level)) {
      return 'Escolha um nível válido para o casual.';
    }
    if (!isCourtPreference(item.court_preference)) {
      return 'Escolha a quadra de cada esporte antes de confirmar.';
    }
  }
  return null;
}

/** Payload único do `PUT`: pares explícitos + preferência de quadra global. */
export function buildSelectionPayload(
  selection: QueueSelection,
  levelFor: (formatId: string, mode: QueueMode) => string | null | undefined,
  courtFor: (formatId: string) => QueueCourtPreference | undefined,
): QueueSelectionPayload {
  // Sem `court_preference` global: a quadra viaja em cada item (ADR 0067).
  return {
    selections: buildSelectionItems(selection, levelFor, courtFor),
  };
}

export function itemsToPairs(items: readonly QueueSelectionItem[]): QueuePair[] {
  return items.map((item) => ({ formatId: item.format_id, mode: item.mode }));
}

/**
 * Compara as entradas confirmadas com a seleção local. A UI usa isto apenas
 * para explicar o efeito do próximo `PUT`; nenhuma entrada é removida antes da
 * confirmação do servidor.
 */
export function queueContinuity(
  entries: readonly QueueEntry[],
  selection: QueueSelection,
): QueueContinuity {
  const pairs = selectionPairs(selection);
  const wanted = new Set(pairs.map((item) => combinationKey(item.formatId, item.mode)));
  const present = new Set<string>();
  const kept: QueueEntry[] = [];
  const removed: QueueEntry[] = [];
  for (const entry of entries) {
    const key = combinationKey(entry.format_id, entryMode(entry));
    present.add(key);
    if (wanted.has(key)) {
      kept.push(entry);
    } else {
      removed.push(entry);
    }
  }
  return {
    kept,
    removed,
    added: pairs.filter((item) => !present.has(combinationKey(item.formatId, item.mode))),
  };
}

/**
 * A seleção pedida está materializada no servidor? Usado só depois de um
 * timeout no `PUT`, para saber se a releitura confirma o commit.
 */
export function snapshotCoversPairs(snapshot: QueueSnapshot, pairs: readonly QueuePair[]): boolean {
  const expected = new Set(pairs.map((item) => combinationKey(item.formatId, item.mode)));
  const actual = new Set<string>();
  for (const entry of snapshot.entries) {
    actual.add(combinationKey(entry.format_id, entryMode(entry)));
  }
  if (snapshot.matched) {
    actual.add(combinationKey(snapshot.matched.format_id, entryMode(snapshot.matched)));
  }
  if (actual.size !== expected.size) {
    return false;
  }
  for (const key of expected) {
    if (!actual.has(key)) {
      return false;
    }
  }
  return true;
}

export function snapshotCoversSelection(
  snapshot: QueueSnapshot,
  selection: QueueSelection,
): boolean {
  return snapshotCoversPairs(snapshot, selectionPairs(selection));
}

export function oldestCreatedAt(entries: readonly QueueEntry[]): string | null {
  let oldest: number | null = null;
  let value: string | null = null;
  for (const entry of entries) {
    const parsed = Date.parse(entry.created_at);
    if (!Number.isFinite(parsed)) {
      continue;
    }
    if (oldest === null || parsed < oldest) {
      oldest = parsed;
      value = entry.created_at;
    }
  }
  return value;
}

export function summarizeEntries(entries: readonly QueueEntry[]): QueueSummary {
  const formats = new Map<string, number>();
  const modes = new Map<QueueMode, number>();
  for (const entry of entries) {
    formats.set(entry.format_id, (formats.get(entry.format_id) ?? 0) + 1);
    const mode = entryMode(entry);
    modes.set(mode, (modes.get(mode) ?? 0) + 1);
  }
  return {
    count: entries.length,
    formats: Array.from(formats, ([formatId, count]) => ({ formatId, count })),
    modes: Array.from(modes, ([mode, count]) => ({ mode, count })),
    oldestCreatedAt: oldestCreatedAt(entries),
  };
}

/**
 * Reconstrói a seleção a partir das entradas confirmadas: um modo por entrada
 * e o nível casual que o servidor devolveu. Não existem pares fantasmas.
 */
export function selectionFromEntries(entries: readonly QueueEntry[]): QueueSelection {
  const formats: string[] = [];
  const byFormat: Record<string, SportQueueChoice> = {};
  for (const entry of entries) {
    const formatId = entry.format_id;
    if (!formatId) {
      continue;
    }
    if (!formats.includes(formatId)) {
      formats.push(formatId);
    }
    const current = byFormat[formatId] ?? { modes: [] };
    const mode = entryMode(entry);
    const court =
      current.court ??
      (isCourtPreference(entry.court_preference) ? entry.court_preference : undefined);
    const fallback: SportQueueChoice = {
      modes: unique<QueueMode>([...current.modes, mode]),
      ...(current.level ? { level: current.level } : {}),
      ...(court ? { court } : {}),
    };
    byFormat[formatId] = fallback;
    if (mode === 'casual' && isQueueLevel(entry.level)) {
      byFormat[formatId] = { ...fallback, level: entry.level };
    }
  }
  for (const formatId of formats) {
    const current = byFormat[formatId];
    byFormat[formatId] = {
      ...current,
      modes: QUEUE_MODES.filter((mode) => current.modes.includes(mode)),
    };
  }
  return { formats, byFormat };
}

/**
 * Formatos com mais de uma quadra diferente entre entradas ativas do mesmo
 * formato (dado legado). A tela unifica na revisão ao confirmar.
 */
export function divergentCourtFormats(entries: readonly QueueEntry[]): string[] {
  const seen: Record<string, Set<QueueCourtPreference>> = {};
  for (const entry of entries) {
    if (!isCourtPreference(entry.court_preference)) {
      continue;
    }
    seen[entry.format_id] = seen[entry.format_id] ?? new Set<QueueCourtPreference>();
    seen[entry.format_id].add(entry.court_preference);
  }
  return Object.keys(seen).filter((formatId) => seen[formatId].size > 1);
}

/** Lobby em jogo para denúncia/reserva: a entrada encontrada tem prioridade. */
export function lobbyIdFromQueue(
  entries: readonly QueueEntry[],
  matched: QueueEntry | null,
): string | null {
  if (matched?.lobby?.id) {
    return matched.lobby.id;
  }
  for (const entry of entries) {
    if (entry.lobby?.id) {
      return entry.lobby.id;
    }
  }
  return null;
}

export function formatLabelFromCatalog(catalog: readonly Sport[], formatId: string): string {
  for (const sport of catalog) {
    const found = sport.formats.find((format) => format.id === formatId);
    if (found) {
      return found.name;
    }
  }
  return 'Formato indisponível';
}

/** Backoff do watcher: 5 → 10 → 20 → 30 s (teto). */
export function nextPollDelay(failures: number, baseMs = 5_000, maxMs = 30_000): number {
  if (failures <= 1) {
    return baseMs;
  }
  return Math.min(maxMs, baseMs * 2 ** Math.min(failures - 1, 4));
}

export function queueCourtPreference(value: string): QueueCourtPreference {
  if (value === 'Públicas') {
    return 'PUBLIC_ONLY';
  }
  if (value === 'Particulares') {
    return 'PRIVATE_ONLY';
  }
  return 'ANY';
}

/** Erros do contrato 0057 traduzidos; nunca expõe código cru ao usuário. */
export function queueFailureMessage(code: string | null | undefined): string {
  switch (code) {
    case 'region_required':
      return 'Defina sua região antes de buscar partida. A seleção atual foi mantida.';
    case 'sport_profile_required':
      return 'Escolha nível e preferência para todos os esportes selecionados. A busca anterior foi mantida.';
    case 'ranked_restricted':
      return 'Ranqueada indisponível no momento. Nada foi alterado: desmarque ranqueada para buscar.';
    case 'invalid_format':
      return 'Um dos esportes não está disponível. Revise a seleção e tente novamente.';
    case 'invalid_mode':
      return 'Modo de partida inválido. Revise a seleção e tente novamente.';
    case 'queue_conflict':
      return 'Já havia uma atualização em andamento. Relemos sua fila; tente novamente.';
    case 'duplicate_queue_selection':
      return 'A mesma combinação de esporte e modo apareceu duas vezes. Revise a seleção.';
    case 'ambiguous_queue_selection':
      return 'A busca foi enviada em um formato ambíguo. Nada foi alterado; tente novamente.';
    case 'invalid_level_override':
      return 'O nível escolhido não pôde ser aplicado. Revise o nível do casual e tente novamente.';
    case 'level_not_applicable_for_ranked':
      return 'Não foi possível montar a busca ranqueada com nível. Nada foi alterado; tente novamente.';
    case 'invalid_court_preference':
      return 'Não foi possível usar essa preferência de quadra. Nada foi alterado; revise a quadra de cada esporte.';
    case 'request_timeout':
    case 'network_unavailable':
      return 'A conexão falhou. Vamos reler sua fila antes de tentar novamente.';
    case 'not_queued':
      return 'Não há buscas ativas.';
    default:
      return 'Não foi possível atualizar a busca. Tente novamente.';
  }
}
