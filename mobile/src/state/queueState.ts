import type {
  QueueCourtPreference,
  QueueEntry,
  QueueLevel,
  QueueLevelAssignment,
  QueueMode,
  QueueStateResponse,
  Sport,
} from '../api/types';

/**
 * Lógica pura da fila multi-entrada (ADR 0057). Nada aqui fala com React ou
 * rede: são funções testáveis por `node --test`.
 *
 * Regra central: a seleção local é intenção; as entradas confirmadas vêm
 * sempre do servidor (`entries` + `entry` legado).
 */

export const QUEUE_MODES: readonly QueueMode[] = ['casual', 'ranked'];

export const QUEUE_LEVELS: readonly QueueLevel[] = ['beginner', 'intermediate', 'advanced'];

export const DEFAULT_QUEUE_MODES: readonly QueueMode[] = ['casual'];

export type QueueSelection = {
  formats: string[];
  modes: QueueMode[];
};

export type QueueCombination = {
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
  /** Entradas confirmadas cuja combinação continua na seleção. */
  kept: QueueEntry[];
  /** Entradas confirmadas que serão canceladas ao confirmar. */
  removed: QueueEntry[];
  /** Combinações da seleção que ainda não existem no servidor. */
  added: QueueCombination[];
};

export function emptySnapshot(): QueueSnapshot {
  return { entries: [], matched: null, expired: [], duplicates: 0 };
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

/** Payload deduplicado e em ordem estável para o `PUT` atômico. */
export function buildSelection(
  formats: readonly string[],
  modes: readonly string[],
): QueueSelection {
  return {
    formats: unique(formats.filter((value) => typeof value === 'string' && value.length > 0)),
    modes: normalizeModes(modes),
  };
}

/** Validação local antes de chamar o servidor; devolve texto acionável. */
export function selectionError(selection: QueueSelection): string | null {
  if (selection.formats.length === 0) {
    return 'Escolha pelo menos um esporte para buscar partida.';
  }
  if (selection.modes.length === 0) {
    return 'Escolha pelo menos um modo: casual ou ranqueada.';
  }
  return null;
}

/** Produto cartesiano usado na prévia ("4 buscas: 2 formatos × 2 modos"). */
export function selectionProduct(selection: QueueSelection): QueueCombination[] {
  const product: QueueCombination[] = [];
  for (const formatId of selection.formats) {
    for (const mode of selection.modes) {
      product.push({ formatId, mode });
    }
  }
  return product;
}

export function selectionProductCount(selection: QueueSelection): number {
  return selection.formats.length * selection.modes.length;
}

export function isExpired(entry: QueueEntry, now: number = Date.now()): boolean {
  const expiresAt = Date.parse(entry.expires_at);
  return Number.isFinite(expiresAt) && expiresAt <= now;
}

export function entryMode(entry: QueueEntry): QueueMode {
  return entry.mode === 'ranked' ? 'ranked' : 'casual';
}

export function modeLabel(mode: QueueMode): string {
  return mode === 'ranked' ? 'Ranqueada' : 'Casual';
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

export function isQueueLevel(value: unknown): value is QueueLevel {
  return value === 'beginner' || value === 'intermediate' || value === 'advanced';
}

export function levelLabel(level: QueueLevel): string {
  if (level === 'beginner') {
    return 'Iniciante';
  }
  return level === 'advanced' ? 'Avançado' : 'Intermediário';
}

/**
 * Uma atribuição explícita de nível por entrada `(format_id, mode)`.
 *
 * `chosen` guarda a escolha local/servidor por chave; `fallback` resolve o
 * default daquela combinação (nível do perfil, por exemplo). Se o valor salvo
 * não for um nível válido, o default é usado; se o default também não for,
 * cai em `intermediate`, o mesmo default da tela de esportes.
 */
export function buildLevelAssignments(
  selection: QueueSelection,
  chosen: Readonly<Record<string, string | undefined>>,
  fallback: (formatId: string, mode: QueueMode) => string | null | undefined,
): QueueLevelAssignment[] {
  return selectionProduct(selection).map(({ formatId, mode }) => {
    const stored = chosen[levelKey(formatId, mode)];
    const candidate = isQueueLevel(stored) ? stored : fallback(formatId, mode);
    return {
      format_id: formatId,
      mode,
      level: isQueueLevel(candidate) ? candidate : 'intermediate',
    };
  });
}

/** Compara duas listas por `(format, mode)`, sem depender da ordem. */
export function levelAssignmentsMatch(
  left: readonly QueueLevelAssignment[],
  right: readonly QueueLevelAssignment[],
): boolean {
  if (left.length !== right.length) {
    return false;
  }
  const byKey = new Map(
    right.map((item) => [levelKey(item.format_id, item.mode), item.level] as const),
  );
  return left.every((item) => byKey.get(levelKey(item.format_id, item.mode)) === item.level);
}

/**
 * Campo `levels` do `PUT`: opcional. Só é enviado quando algum nível escolhido
 * difere do default do servidor; nesse caso leva **todas** as entradas
 * selecionadas, para a revisão e o payload serem idênticos.
 */
export function optionalLevelsPayload(
  assignments: readonly QueueLevelAssignment[],
  serverDefaults: readonly QueueLevelAssignment[],
): QueueLevelAssignment[] | undefined {
  return levelAssignmentsMatch(assignments, serverDefaults) ? undefined : [...assignments];
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
  const product = selectionProduct(selection);
  const wanted = new Set(product.map((item) => combinationKey(item.formatId, item.mode)));
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
    added: product.filter((item) => !present.has(combinationKey(item.formatId, item.mode))),
  };
}

/**
 * A seleção pedida está materializada no servidor? Usado só depois de um
 * timeout no `PUT`, para saber se a releitura confirma o commit.
 */
export function snapshotCoversSelection(
  snapshot: QueueSnapshot,
  selection: QueueSelection,
): boolean {
  const expected = new Set(
    selectionProduct(selection).map((item) => combinationKey(item.formatId, item.mode)),
  );
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

export function selectionFromEntries(entries: readonly QueueEntry[]): QueueSelection {
  const formats: string[] = [];
  const modes: QueueMode[] = [];
  for (const entry of entries) {
    if (!formats.includes(entry.format_id)) {
      formats.push(entry.format_id);
    }
    const mode = entryMode(entry);
    if (!modes.includes(mode)) {
      modes.push(mode);
    }
  }
  return { formats, modes };
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
    case 'request_timeout':
    case 'network_unavailable':
      return 'A conexão falhou. Vamos reler sua fila antes de tentar novamente.';
    case 'not_queued':
      return 'Não há buscas ativas.';
    default:
      return 'Não foi possível atualizar a busca. Tente novamente.';
  }
}
