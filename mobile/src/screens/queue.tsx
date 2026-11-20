import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { View } from 'react-native';

import { describeApiError, ApiError } from '../api/client';
import type { QueueEntry, QueueLevel, QueueMode, Sport } from '../api/types';
import { useApp } from '../state/app';
import { useNav, useTheme } from '../state/context';
import {
  QUEUE_LEVELS,
  QUEUE_MODES,
  buildLevelAssignments,
  buildSelection,
  entryMode,
  formatLabelFromCatalog,
  isQueueLevel,
  levelKey,
  levelLabel,
  modeLabel,
  oldestCreatedAt,
  optionalLevelsPayload,
  queueContinuity,
  queueCourtPreference,
  queueFailureMessage,
  selectionError,
  selectionFromEntries,
  selectionProductCount,
} from '../state/queueState';
import { useActiveInterval } from '../state/useActiveInterval';
import { divisionLabel, elapsed, timeOnly, WEEKDAY_NAMES } from '../ui/datetime';
import {
  Badge,
  Btn,
  BtnRow,
  Card,
  Chip,
  ChipRow,
  EmptyState,
  LoadingState,
  Notice,
  Page,
  Row,
  TextBtn,
  Txt,
} from '../ui/kit';
import { Text } from '../ui/text';

const COURT_OPTIONS = ['Públicas', 'Particulares', 'Tanto faz'] as const;
type CourtChoice = (typeof COURT_OPTIONS)[number];

type QueueStep = 1 | 2;
type QueueView = 'overview' | 'edit';

type QueueDraft = {
  step: QueueStep;
  formats: string[];
  modes: QueueMode[];
  levels: Record<string, QueueLevel>;
  court: CourtChoice;
};

/**
 * Rascunho da seleção ainda não confirmada. Vive só em memória: sair da tela
 * (inclusive pelo back do Android) não descarta a escolha do usuário, mas nada
 * é enviado ao servidor sem o toque em "Confirmar busca".
 */
let queueDraft: QueueDraft | null = null;

type LevelRow = { mode: QueueMode; level: QueueLevel };

function formatName(catalog: readonly Sport[], formatId: string): string {
  return formatLabelFromCatalog(catalog, formatId);
}

function modesLabel(modes: readonly QueueMode[]): string {
  const selected = QUEUE_MODES.filter((mode) => modes.includes(mode));
  return selected.length > 0 ? selected.map(modeLabel).join(' e ') : 'Escolha ao menos um';
}

function ConfigLine({ label, value }: { label: string; value: string }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 10 }}>
      <Txt variant="tiny" style={{ width: 86 }}>
        {label}
      </Txt>
      <Txt variant="tiny" weight="800" align="right" style={{ flex: 1, minWidth: 0 }}>
        {value}
      </Txt>
    </View>
  );
}

function SportConfigCard({
  formatId,
  catalog,
  levelRows,
  court,
  profileReady,
  kept,
  removed,
  onCompleteProfile,
  onLevelChange,
}: {
  formatId: string;
  catalog: readonly Sport[];
  levelRows: readonly LevelRow[];
  court: CourtChoice;
  profileReady: boolean | null;
  kept: QueueEntry[];
  removed: QueueEntry[];
  onCompleteProfile: () => void;
  onLevelChange: (mode: QueueMode, level: QueueLevel) => void;
}) {
  return (
    <Card>
      <Txt variant="lead" weight="800">
        {formatName(catalog, formatId)}
      </Txt>
      <View style={{ marginTop: 10, gap: 8 }}>
        <ConfigLine label="Modos" value={modesLabel(levelRows.map((row) => row.mode))} />
        <ConfigLine label="Quadra" value={court} />
        <ConfigLine
          label="Perfil"
          value={
            profileReady === null
              ? 'Carregando perfil'
              : profileReady
                ? 'Pronto para buscar'
                : 'Falta nível e preferência'
          }
        />
        {kept.map((entry) => (
          <ConfigLine
            key={`kept-${entry.id}`}
            label="Busca ativa"
            value={`${modeLabel(entryMode(entry))} continua · desde ${timeOnly(entry.created_at)}`}
          />
        ))}
        {removed.map((entry) => (
          <ConfigLine
            key={`removed-${entry.id}`}
            label="Ao confirmar"
            value={`${modeLabel(entryMode(entry))} será cancelada`}
          />
        ))}
      </View>
      {levelRows.map((row) => (
        <View key={row.mode} style={{ marginTop: 12, gap: 6 }}>
          <Txt variant="label">Nível no {modeLabel(row.mode).toLowerCase()}</Txt>
          <ChipRow>
            {QUEUE_LEVELS.map((option) => (
              <Chip
                key={option}
                on={row.level === option}
                accessibilityLabel={`Nível no ${modeLabel(row.mode).toLowerCase()}: ${levelLabel(option)}`}
                onPress={() => onLevelChange(row.mode, option)}
              >
                {levelLabel(option)}
              </Chip>
            ))}
          </ChipRow>
        </View>
      ))}
      {profileReady === false ? (
        <TextBtn onPress={onCompleteProfile}>Completar este esporte</TextBtn>
      ) : null}
    </Card>
  );
}

export function QueueScreen() {
  const nav = useNav();
  const {
    catalog,
    profile,
    wallet,
    ratings,
    primaryFormatId,
    loadRating,
    loadCatalog,
    session,
    queue,
    matchedEntry,
    replaceQueue,
    loadQueue,
    clearQueueNotice,
    queueNotice,
  } = useApp();
  const initialModes = useMemo<QueueMode[]>(
    () => (nav.params.mode === 'ranked' ? ['ranked'] : ['casual']),
    [nav.params.mode],
  );
  // Lido uma única vez, no primeiro render: o rascunho sobrevive à saída da
  // tela sem virar fonte de verdade do servidor.
  const draftAtMount = queueDraft;
  const [view, setView] = useState<QueueView>(() =>
    draftAtMount || nav.params.from === 'queue-search' ? 'edit' : 'overview',
  );
  const [step, setStep] = useState<QueueStep>(() => draftAtMount?.step ?? 1);
  const [selected, setSelected] = useState<string[]>(() => draftAtMount?.formats ?? []);
  const [modes, setModes] = useState<QueueMode[]>(() => draftAtMount?.modes ?? initialModes);
  const [levels, setLevels] = useState<Record<string, QueueLevel>>(
    () => draftAtMount?.levels ?? {},
  );
  const [court, setCourt] = useState<CourtChoice>(() => draftAtMount?.court ?? 'Tanto faz');
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [syncing, setSyncing] = useState(() => !!session);
  const [syncError, setSyncError] = useState(false);
  const [catalogLoading, setCatalogLoading] = useState(() => catalog.length === 0);
  const [failure, setFailure] = useState<{ code: string; message: string } | null>(null);
  const [now, setNow] = useState(() => new Date());
  const touched = useRef(!!draftAtMount);
  const synced = useRef(false);

  const formats = useMemo(() => catalog.flatMap((sport) => sport.formats), [catalog]);
  const optionById = useMemo(
    () => new Map(formats.map((format) => [format.id, format])),
    [formats],
  );
  const profileFormatIds = useMemo(
    () => (profile?.sports ?? []).map((sport) => sport.format_id),
    [profile],
  );
  const serverLevels = useMemo(() => {
    const map: Record<string, QueueLevel> = {};
    for (const entry of queue) {
      if (isQueueLevel(entry.level)) {
        map[levelKey(entry.format_id, entryMode(entry))] = entry.level;
      }
    }
    return map;
  }, [queue]);
  const catalogBusy = catalogLoading && formats.length === 0;

  const retryCatalog = useCallback(async () => {
    setCatalogLoading(true);
    try {
      await loadCatalog();
    } catch (cause) {
      if (__DEV__) {
        console.warn('Falha ao carregar /sports', describeApiError(cause));
      }
    } finally {
      setCatalogLoading(false);
    }
  }, [loadCatalog]);

  useEffect(() => {
    if (catalog.length > 0) {
      return;
    }
    let active = true;
    loadCatalog()
      .catch((cause) => {
        if (__DEV__) {
          console.warn('Falha ao carregar /sports', describeApiError(cause));
        }
      })
      .finally(() => {
        if (active) {
          setCatalogLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [catalog.length, loadCatalog]);

  const reloadQueue = useCallback(async () => {
    setSyncing(true);
    setSyncError(false);
    try {
      await loadQueue();
      setNow(new Date());
    } catch (cause) {
      setSyncError(true);
      if (__DEV__) {
        console.warn('GET /matchmaking/queue falhou', describeApiError(cause));
      }
    } finally {
      setSyncing(false);
    }
  }, [loadQueue]);

  // Reconcilia com o servidor ao montar; a lista exibida nunca vem de
  // `nav.params` nem da seleção local.
  useEffect(() => {
    if (!session) {
      queueDraft = null;
      return;
    }
    if (synced.current) {
      return;
    }
    synced.current = true;
    void reloadQueue();
  }, [reloadQueue, session]);

  // A seleção local só adota o servidor enquanto o usuário não mexeu. Com
  // fila ativa, o fluxo abre no resumo; a edição parte das entradas reais.
  useEffect(() => {
    if (touched.current) {
      return;
    }
    if (queue.length > 0) {
      const fromQueue = selectionFromEntries(queue);
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSelected(fromQueue.formats.filter((id) => optionById.has(id)));
      setModes(fromQueue.modes.length > 0 ? fromQueue.modes : initialModes);
      // O nível default de cada modo vem do servidor; escolha local posterior
      // nunca é sobrescrita porque este efeito só roda antes de `touched`.
      setLevels(serverLevels);
      return;
    }
    setSelected((current) => {
      if (current.length > 0) {
        return current;
      }
      if (primaryFormatId && optionById.has(primaryFormatId)) {
        return [primaryFormatId];
      }
      return formats.length > 0 ? [formats[0].id] : [];
    });
  }, [formats, initialModes, optionById, primaryFormatId, queue, serverLevels]);

  const selection = useMemo(() => buildSelection(selected, modes), [modes, selected]);
  const count = selectionProductCount(selection);
  const continuity = useMemo(() => queueContinuity(queue, selection), [queue, selection]);
  const hasConfirmed = queue.length > 0 || matchedEntry !== null;
  const showOverview = view === 'overview' && hasConfirmed && !syncing;
  const rankedSelected = selection.modes.includes('ranked');

  const profileLevelFor = useCallback(
    (formatId: string) => profile?.sports.find((sport) => sport.format_id === formatId)?.level,
    [profile],
  );

  // Default por `(format, mode)`: level já confirmado no servidor para aquela
  // entrada; na ausência dele, o nível do perfil do formato.
  const defaultLevelFor = useCallback(
    (formatId: string, mode: QueueMode): string | undefined =>
      serverLevels[levelKey(formatId, mode)] ?? profileLevelFor(formatId),
    [profileLevelFor, serverLevels],
  );

  const levelAssignments = useMemo(
    () => buildLevelAssignments(selection, levels, defaultLevelFor),
    [defaultLevelFor, levels, selection],
  );

  // Default que o backend aplica quando `levels` está ausente: nível do perfil.
  const backendDefaults = useMemo(
    () => buildLevelAssignments(selection, {}, (formatId) => profileLevelFor(formatId)),
    [profileLevelFor, selection],
  );

  // Só envia o campo opcional quando a revisão difere do default do servidor;
  // quando envia, vai uma atribuição explícita para cada entrada selecionada.
  const payloadLevels = useMemo(
    () => optionalLevelsPayload(levelAssignments, backendDefaults),
    [backendDefaults, levelAssignments],
  );

  const levelRowsFor = useCallback(
    (formatId: string): LevelRow[] =>
      selection.modes.map((mode) => ({
        mode,
        level:
          levelAssignments.find((item) => item.format_id === formatId && item.mode === mode)
            ?.level ?? 'intermediate',
      })),
    [levelAssignments, selection.modes],
  );

  // Mantém o rascunho enquanto o usuário está no formulário. O servidor só é
  // alterado no `PUT` de confirmação.
  useEffect(() => {
    if (view !== 'edit') {
      return;
    }
    queueDraft = { step, formats: selected, modes, levels, court };
  }, [court, levels, modes, selected, step, view]);

  const selectedFormatId = selection.formats[0] ?? primaryFormatId ?? formats[0]?.id ?? null;
  const rating = selectedFormatId ? ratings[selectedFormatId] : undefined;
  const ratingsRef = useRef(ratings);
  const requestedRatings = useRef(new Set<string>());

  useEffect(() => {
    ratingsRef.current = ratings;
  }, [ratings]);

  useEffect(() => {
    if (!rankedSelected || !selectedFormatId) {
      return;
    }
    if (ratingsRef.current[selectedFormatId] || requestedRatings.current.has(selectedFormatId)) {
      return;
    }
    requestedRatings.current.add(selectedFormatId);
    loadRating(selectedFormatId).catch(() => {
      requestedRatings.current.delete(selectedFormatId);
    });
  }, [loadRating, rankedSelected, selectedFormatId]);

  const windows = profile?.availability ?? [];
  const firstWindow = windows[0];
  const availabilityTitle = firstWindow
    ? `${WEEKDAY_NAMES[firstWindow.weekday - 1]} · ${firstWindow.start_time.slice(0, 5)}–${firstWindow.end_time.slice(0, 5)}`
    : 'Nenhum horário cadastrado';
  const availabilitySub =
    windows.length > 0
      ? `${windows.length} ${windows.length === 1 ? 'janela' : 'janelas'} na semana`
      : 'Adicione quando você costuma jogar';

  const markTouched = useCallback(() => {
    touched.current = true;
    setFailure(null);
  }, []);

  const toggleFormat = useCallback(
    (formatId: string) => {
      markTouched();
      setSelected((current) =>
        current.includes(formatId)
          ? current.filter((value) => value !== formatId)
          : [...current, formatId],
      );
    },
    [markTouched],
  );

  const toggleMode = useCallback(
    (mode: QueueMode) => {
      markTouched();
      setModes((current) =>
        current.includes(mode) ? current.filter((value) => value !== mode) : [...current, mode],
      );
    },
    [markTouched],
  );

  const chooseCourt = useCallback(
    (value: CourtChoice) => {
      markTouched();
      setCourt(value);
    },
    [markTouched],
  );

  const changeLevel = useCallback(
    (formatId: string, mode: QueueMode, level: QueueLevel) => {
      markTouched();
      // Preserva as outras combinações (inclusive modos desmarcados): remover
      // ranqueada e adicioná-la de novo não apaga o nível já escolhido.
      setLevels((current) => ({ ...current, [levelKey(formatId, mode)]: level }));
    },
    [markTouched],
  );

  const startEdit = useCallback(() => {
    touched.current = true;
    setFailure(null);
    setView('edit');
    setStep(1);
    if (queue.length > 0) {
      const fromQueue = selectionFromEntries(queue);
      setSelected(fromQueue.formats.filter((id) => optionById.has(id)));
      if (fromQueue.modes.length > 0) {
        setModes(fromQueue.modes);
      }
      setLevels(serverLevels);
    }
  }, [optionById, queue, serverLevels]);

  const backToOverview = useCallback(() => {
    setFailure(null);
    setView('overview');
    setNow(new Date());
  }, []);

  const goToStep2 = useCallback(() => {
    const problem = selectionError(selection);
    if (problem) {
      setFailure({ code: 'invalid_selection', message: problem });
      return;
    }
    setFailure(null);
    setStep(2);
  }, [selection]);

  const submit = useCallback(async () => {
    if (busyRef.current) {
      return;
    }
    if (!session) {
      nav.toast('Entre na sua conta para buscar partida.');
      return;
    }
    const problem = selectionError(selection);
    if (problem) {
      setFailure({ code: 'invalid_selection', message: problem });
      return;
    }
    busyRef.current = true;
    setBusy(true);
    setFailure(null);
    clearQueueNotice();
    try {
      // Uma única chamada: o servidor substitui todas as entradas de uma vez.
      const result = await replaceQueue(
        selection.formats,
        selection.modes,
        queueCourtPreference(court),
        payloadLevels,
      );
      if (result.ok) {
        touched.current = false;
        queueDraft = null;
        if (nav.params.from === 'queue-search') {
          nav.back();
        } else {
          nav.replace('queue-search', {});
        }
        return;
      }
      if (__DEV__) {
        console.warn('PUT /matchmaking/queue falhou', result.code);
      }
      setFailure({ code: result.code, message: queueFailureMessage(result.code) });
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }, [clearQueueNotice, court, nav, payloadLevels, replaceQueue, selection, session]);

  useActiveInterval(() => setNow(new Date()), 1000, showOverview && queue.length > 0);

  const stepOneBack =
    hasConfirmed && !(nav.params.from === 'queue-search' && nav.canGoBack) ? backToOverview : null;

  if (syncing) {
    return (
      <Page title="Buscar partida" sub="Sincronizando suas buscas">
        <LoadingState label="Sincronizando suas buscas ativas com o servidor…" />
      </Page>
    );
  }

  if (showOverview) {
    const oldest = oldestCreatedAt(queue);
    return (
      <Page title="Buscar partida" sub="Suas buscas ativas">
        {syncError ? (
          <View style={{ gap: 8 }}>
            <Notice tone="orange" icon="alert">
              Não foi possível reler suas buscas no servidor.
            </Notice>
            <TextBtn onPress={() => void reloadQueue()}>Tentar novamente</TextBtn>
          </View>
        ) : null}
        <Card tone="blue">
          <Row between>
            <Txt variant="label">Buscas ativas</Txt>
            <Badge>{queue.length}</Badge>
          </Row>
          <Txt variant="h2" style={{ marginTop: 4 }}>
            {queue.length} {queue.length === 1 ? 'busca ativa' : 'buscas ativas'}
          </Txt>
          {queue.length > 0 ? (
            <View style={{ marginTop: 8, gap: 4 }}>
              {queue.map((entry) => (
                <Txt key={entry.id} variant="tiny">
                  {formatName(catalog, entry.format_id)} · {modeLabel(entryMode(entry))}
                  {isQueueLevel(entry.level) ? ` · ${levelLabel(entry.level)}` : ''}
                </Txt>
              ))}
            </View>
          ) : null}
          {oldest ? (
            <Txt variant="tiny" style={{ marginTop: 4 }}>
              Mais antiga: {elapsed(oldest, now)}
            </Txt>
          ) : null}
          {matchedEntry ? (
            <View style={{ marginTop: 10 }}>
              <Txt variant="label">Partida encontrada</Txt>
              <Txt variant="lead" weight="800">
                {formatName(catalog, matchedEntry.format_id)} · {modeLabel(entryMode(matchedEntry))}
                {isQueueLevel(matchedEntry.level) ? ` · ${levelLabel(matchedEntry.level)}` : ''}
              </Txt>
              <Txt variant="tiny">
                As demais buscas continuam aguardando. A entrada encontrada vem do servidor.
              </Txt>
            </View>
          ) : null}
        </Card>
        {queueNotice ? (
          <View style={{ gap: 8 }}>
            <Notice tone="orange" icon="alert">
              {queueNotice}
            </Notice>
            <TextBtn muted onPress={clearQueueNotice}>
              Dispensar aviso
            </TextBtn>
          </View>
        ) : null}
        <Btn tone="primary" icon="search" onPress={startEdit}>
          Editar busca
        </Btn>
        <TextBtn onPress={() => nav.go('queue-search')}>Acompanhar busca</TextBtn>
      </Page>
    );
  }

  const sub = step === 1 ? 'Passo 1 de 2 · Esportes' : 'Passo 2 de 2 · Ajustes';

  return (
    <Page title="Buscar partida" sub={sub}>
      {syncError ? (
        <View style={{ gap: 8 }}>
          <Notice tone="orange" icon="alert">
            Não foi possível reler suas buscas no servidor.
          </Notice>
          <TextBtn onPress={() => void reloadQueue()}>Tentar novamente</TextBtn>
        </View>
      ) : null}
      {queueNotice ? (
        <View style={{ gap: 8 }}>
          <Notice tone="orange" icon="alert">
            {queueNotice}
          </Notice>
          <TextBtn muted onPress={clearQueueNotice}>
            Dispensar aviso
          </TextBtn>
        </View>
      ) : null}

      {step === 1 ? (
        <>
          <Card>
            <Row between>
              <Txt variant="h3">Esportes</Txt>
              <Txt variant="tiny">{formats.length} no catálogo</Txt>
            </Row>
            {catalogBusy ? (
              <LoadingState label="Carregando esportes…" />
            ) : formats.length === 0 ? (
              <View style={{ gap: 8, marginTop: 8 }}>
                <Txt variant="tiny">
                  Não foi possível carregar o catálogo de esportes agora. Tente novamente em
                  instantes.
                </Txt>
                <TextBtn onPress={() => void retryCatalog()}>Tentar novamente</TextBtn>
              </View>
            ) : (
              <ChipRow style={{ marginTop: 8 }}>
                {formats.map((format) => (
                  <Chip
                    key={format.id}
                    on={selected.includes(format.id)}
                    onPress={() => toggleFormat(format.id)}
                  >
                    {format.name}
                  </Chip>
                ))}
              </ChipRow>
            )}
          </Card>

          <Card tone="flat">
            <Row between>
              <Txt variant="label">Serão enviadas</Txt>
              <Badge>{count}</Badge>
            </Row>
            <Txt variant="num" style={{ marginTop: 4 }}>
              {count} {count === 1 ? 'busca' : 'buscas'}
            </Txt>
            <Txt variant="tiny" style={{ marginTop: 4 }}>
              {selection.formats.length} {selection.formats.length === 1 ? 'esporte' : 'esportes'} ×{' '}
              {selection.modes.length} {selection.modes.length === 1 ? 'modo' : 'modos'}.
              {selection.modes.length > 0 ? ` ${modesLabel(selection.modes)}.` : ''}
            </Txt>
            {hasConfirmed && continuity.kept.length > 0 ? (
              <Txt variant="tiny" style={{ marginTop: 6 }}>
                {continuity.kept.length}{' '}
                {continuity.kept.length === 1 ? 'busca ativa continua' : 'buscas ativas continuam'}{' '}
                com o mesmo tempo de espera.
              </Txt>
            ) : null}
            {hasConfirmed && continuity.removed.length > 0 ? (
              <Txt variant="tiny" style={{ marginTop: 4 }}>
                {continuity.removed.length}{' '}
                {continuity.removed.length === 1
                  ? 'busca ativa será cancelada'
                  : 'buscas ativas serão canceladas'}{' '}
                ao confirmar.
              </Txt>
            ) : null}
          </Card>

          {failure ? (
            <View style={{ gap: 8 }}>
              <Notice tone="orange" icon="alert">
                {failure.message}
              </Notice>
            </View>
          ) : null}

          <Btn
            tone="primary"
            onPress={goToStep2}
            disabled={catalogBusy || formats.length === 0 || selectionError(selection) !== null}
          >
            Continuar
          </Btn>
          {stepOneBack ? <TextBtn onPress={stepOneBack}>Voltar</TextBtn> : null}
        </>
      ) : (
        <>
          <Card tone="flat">
            <Txt variant="h2">Ajuste cada esporte</Txt>
            <Txt variant="tiny" style={{ marginTop: 4 }}>
              Modos e quadra valem para todos. O horário de disponibilidade é único e também vale
              para todos.
            </Txt>
          </Card>

          {matchedEntry ? (
            <Card tone="blue">
              <Row between>
                <Txt variant="label">Partida encontrada</Txt>
                <Badge>enquanto você ajustava</Badge>
              </Row>
              <Txt variant="lead" weight="800">
                {formatName(catalog, matchedEntry.format_id)} · {modeLabel(entryMode(matchedEntry))}
                {isQueueLevel(matchedEntry.level) ? ` · ${levelLabel(matchedEntry.level)}` : ''}
              </Txt>
              <Txt variant="tiny">
                As demais buscas continuam aguardando; esta é a entrada que o servidor fechou.
              </Txt>
              <TextBtn onPress={() => nav.go('queue-search')}>Ver partida</TextBtn>
            </Card>
          ) : null}

          <Card tone="blue">
            <Row between>
              <View style={{ flex: 1, minWidth: 0 }}>
                <Txt variant="h3">Vale para todos os esportes</Txt>
                <Txt variant="tiny" style={{ marginTop: 4 }}>
                  Modos e quadra são compartilhados. O nível é definido em cada esporte.
                </Txt>
              </View>
              <Badge>compartilhado</Badge>
            </Row>
            <Txt variant="label" style={{ marginTop: 10 }}>
              Modos
            </Txt>
            <ChipRow style={{ marginTop: 8 }}>
              {QUEUE_MODES.map((mode) => (
                <Chip
                  key={mode}
                  on={selection.modes.includes(mode)}
                  onPress={() => toggleMode(mode)}
                >
                  {modeLabel(mode)}
                </Chip>
              ))}
            </ChipRow>
            <Txt variant="tiny" style={{ marginTop: 8 }}>
              Cada modo vira uma busca separada para cada esporte.
            </Txt>
            {rankedSelected ? (
              <Txt variant="tiny" style={{ marginTop: 4 }}>
                Sua divisão:{' '}
                {rating?.provisional
                  ? 'provisória'
                  : rating
                    ? divisionLabel(rating.division)
                    : 'carregando'}
                . Ranqueada considera sua divisão e compatibilidade.
              </Txt>
            ) : null}
            <Txt variant="label" style={{ marginTop: 12 }}>
              Preferência de quadra
            </Txt>
            <ChipRow style={{ marginTop: 8 }}>
              {COURT_OPTIONS.map((item) => (
                <Chip key={item} on={court === item} onPress={() => chooseCourt(item)}>
                  {item}
                </Chip>
              ))}
            </ChipRow>
          </Card>

          {selection.formats.map((formatId) => (
            <SportConfigCard
              key={formatId}
              formatId={formatId}
              catalog={catalog}
              levelRows={levelRowsFor(formatId)}
              court={court}
              profileReady={profile ? profileFormatIds.includes(formatId) : null}
              kept={continuity.kept.filter((entry) => entry.format_id === formatId)}
              removed={continuity.removed.filter((entry) => entry.format_id === formatId)}
              onCompleteProfile={() => nav.go('sports')}
              onLevelChange={(mode, level) => changeLevel(formatId, mode, level)}
            />
          ))}

          <Card>
            <Row between>
              <Txt variant="h3">Horário de disponibilidade</Txt>
              <Badge>para todos</Badge>
            </Row>
            <Txt variant="lead" weight="800" style={{ marginTop: 8 }}>
              {availabilityTitle}
            </Txt>
            <Txt variant="tiny">{availabilitySub}</Txt>
            <Txt variant="tiny" style={{ marginTop: 6 }}>
              O mesmo horário vale para todos os esportes; não há horário por esporte.
            </Txt>
            <TextBtn onPress={() => nav.go('availability')}>
              {windows.length > 0 ? 'Editar horários' : 'Adicionar horários'}
            </TextBtn>
          </Card>

          <Card>
            <Row between>
              <Txt variant="h3">Região</Txt>
              <Badge>{profile?.region ? `${profile.region.radius_km} km` : 'definir'}</Badge>
            </Row>
            <Txt variant="lead" weight="800" style={{ marginTop: 8 }}>
              {profile?.region?.city ?? 'Sem região definida'}
            </Txt>
            <Txt variant="tiny">
              {profile?.region
                ? 'A busca usa sua região e o raio definido.'
                : 'Defina sua região para buscar partida.'}
            </Txt>
            <TextBtn onPress={() => nav.go('region')}>
              {profile?.region ? 'Trocar região' : 'Definir região'}
            </TextBtn>
          </Card>

          <Card tone="flat">
            <Row between>
              <Txt variant="label">Custo estimado</Txt>
              <Badge tone="lime">saldo {wallet?.balance ?? 18}</Badge>
            </Row>
            <Txt variant="num" style={{ marginTop: 4 }}>
              7 ingressos
            </Txt>
            <Txt variant="tiny">O valor final aparece na confirmação da vaga.</Txt>
          </Card>

          <Card tone="flat">
            <Row between>
              <Txt variant="label">Revisão</Txt>
              <Badge>{count}</Badge>
            </Row>
            <Txt variant="h2" style={{ marginTop: 4 }}>
              {count} {count === 1 ? 'busca' : 'buscas'}
            </Txt>
            {levelAssignments.length === 0 ? (
              <Txt variant="tiny" style={{ marginTop: 6 }}>
                Escolha pelo menos um esporte e um modo para continuar.
              </Txt>
            ) : (
              <View style={{ marginTop: 10, gap: 8 }}>
                {levelAssignments.map((assignment) => (
                  <Txt
                    key={`${assignment.format_id}:${assignment.mode}`}
                    variant="sub"
                    style={{ flexShrink: 1 }}
                  >
                    {formatName(catalog, assignment.format_id)} · {modeLabel(assignment.mode)} ·{' '}
                    {levelLabel(assignment.level)}
                  </Txt>
                ))}
              </View>
            )}
            {continuity.kept.length > 0 ? (
              <Txt variant="tiny" style={{ marginTop: 10 }}>
                {continuity.kept.length}{' '}
                {continuity.kept.length === 1
                  ? 'busca já ativa continua'
                  : 'buscas já ativas continuam'}{' '}
                com o mesmo tempo de espera.
              </Txt>
            ) : null}
            {continuity.removed.length > 0 ? (
              <Txt variant="tiny" style={{ marginTop: 4 }}>
                {continuity.removed.length}{' '}
                {continuity.removed.length === 1
                  ? 'busca ativa será cancelada'
                  : 'buscas ativas serão canceladas'}{' '}
                ao confirmar.
              </Txt>
            ) : null}
          </Card>

          {failure ? (
            <View style={{ gap: 8 }}>
              <Notice tone="orange" icon="alert">
                {failure.message}
              </Notice>
              {failure.code === 'region_required' ? (
                <TextBtn onPress={() => nav.go('region')}>Definir região</TextBtn>
              ) : failure.code === 'sport_profile_required' ? (
                <TextBtn onPress={() => nav.go('sports')}>Completar modalidades</TextBtn>
              ) : failure.code === 'ranked_restricted' ? (
                <TextBtn
                  onPress={() => {
                    setModes(['casual']);
                    setFailure(null);
                  }}
                >
                  Buscar só casual
                </TextBtn>
              ) : failure.code === 'network_unavailable' || failure.code === 'request_timeout' ? (
                <TextBtn onPress={() => void reloadQueue()}>Reler fila</TextBtn>
              ) : null}
            </View>
          ) : null}

          <Btn
            tone="primary"
            icon="search"
            onPress={submit}
            disabled={busy || count === 0 || selection.formats.length === 0}
          >
            {busy ? 'Atualizando busca…' : hasConfirmed ? 'Atualizar busca' : 'Confirmar busca'}
          </Btn>
          <TextBtn onPress={() => setStep(1)}>Voltar</TextBtn>
        </>
      )}
    </Page>
  );
}

export function QueueSearch() {
  const nav = useNav();
  const { palette } = useTheme();
  const {
    queue,
    matchedEntry,
    loadQueue,
    cancelQueue,
    session,
    profile,
    catalog,
    queueReconnecting,
    queueNotice,
    clearQueueNotice,
  } = useApp();
  const [now, setNow] = useState(() => new Date());
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(() => queue.length === 0 && !matchedEntry);
  const routed = useRef<string | null>(null);

  const oldest = oldestCreatedAt(queue);
  useActiveInterval(() => setNow(new Date()), 1000, queue.length > 0);

  useEffect(() => {
    if (!session) {
      return;
    }
    let active = true;
    loadQueue()
      .then(() => {
        if (active) {
          setError(null);
        }
      })
      .catch((cause) => {
        if (active) {
          const code = cause instanceof ApiError ? cause.code : 'network_unavailable';
          setError(queueFailureMessage(code));
          if (__DEV__) {
            console.warn('GET /matchmaking/queue falhou', describeApiError(cause));
          }
        }
      })
      .finally(() => {
        if (active) {
          setSyncing(false);
        }
      });
    return () => {
      active = false;
    };
  }, [session, loadQueue]);

  // A navegação para a partida é consequência do estado do servidor; nunca
  // escolhemos vencedor de empate.
  useEffect(() => {
    if (nav.id !== 'queue-search') {
      return;
    }
    const lobby = matchedEntry?.lobby;
    if (!lobby || routed.current === lobby.id) {
      return;
    }
    routed.current = lobby.id;
    nav.replace('lobby-found', { lobbyId: lobby.id, mode: matchedEntry.mode });
  }, [matchedEntry, nav]);

  const cancel = async () => {
    if (busy) {
      return;
    }
    setBusy(true);
    setError(null);
    const result = await cancelQueue();
    if (result.ok) {
      setBusy(false);
      nav.reset('home');
      nav.toast('Buscas canceladas.');
      return;
    }
    if (__DEV__) {
      console.warn('DELETE /matchmaking/queue falhou', result.code);
    }
    setError(queueFailureMessage(result.code));
    setBusy(false);
  };

  const reload = async () => {
    setError(null);
    try {
      await loadQueue();
    } catch (cause) {
      const code = cause instanceof ApiError ? cause.code : 'network_unavailable';
      setError(queueFailureMessage(code));
    }
  };

  const grouped = useMemo(() => {
    const casual = queue.filter((entry) => entryMode(entry) === 'casual');
    const ranked = queue.filter((entry) => entryMode(entry) === 'ranked');
    const groups: { mode: QueueMode; entries: typeof queue }[] = [];
    if (casual.length > 0) {
      groups.push({ mode: 'casual', entries: casual });
    }
    if (ranked.length > 0) {
      groups.push({ mode: 'ranked', entries: ranked });
    }
    return groups;
  }, [queue]);

  const renderEntry = (entry: (typeof queue)[number]) => (
    <Row key={entry.id} between>
      <View style={{ flex: 1, minWidth: 0 }}>
        <Text numberOfLines={2} style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
          {formatName(catalog, entry.format_id)}
        </Text>
        <Text style={{ fontSize: 12, color: palette.muted }}>
          {entry.radius_km} km · desde {timeOnly(entry.created_at)}
        </Text>
      </View>
      <Text style={{ fontSize: 15, fontWeight: '800', color: palette.ink }}>
        {elapsed(entry.created_at, now)}
      </Text>
    </Row>
  );

  if (queue.length === 0 && !matchedEntry) {
    if (syncing) {
      return (
        <Page title="Buscas ativas">
          <LoadingState label="Sincronizando sua fila com o servidor…" />
        </Page>
      );
    }
    return (
      <Page title="Buscas ativas">
        <EmptyState
          title="Nenhuma busca ativa"
          text="O servidor não tem entradas aguardando para você. Se você acabou de cancelar, está tudo certo. Para procurar de novo, monte a seleção de esportes e modos."
          actions={
            <Btn tone="primary" onPress={() => nav.go('queue', { from: 'queue-search' })}>
              Buscar partida
            </Btn>
          }
        />
        {error ? (
          <>
            <Notice tone="orange" icon="alert">
              {error}
            </Notice>
            <Btn tone="ghost" onPress={reload}>
              Reler fila
            </Btn>
          </>
        ) : null}
        {queueNotice ? (
          <Notice tone="orange" icon="alert">
            {queueNotice}
          </Notice>
        ) : null}
      </Page>
    );
  }

  const modeCount = grouped.length;
  const cancelTarget = queue.length;

  return (
    <Page title="Buscas ativas">
      {matchedEntry ? (
        <Card tone="blue">
          <Row between>
            <Txt variant="label">Partida encontrada</Txt>
            <Badge>servidor</Badge>
          </Row>
          <Text
            numberOfLines={2}
            style={{ fontSize: 20, lineHeight: 24, fontWeight: '900', color: palette.ink }}
          >
            {formatName(catalog, matchedEntry.format_id)} · {modeLabel(entryMode(matchedEntry))}
          </Text>
          <Txt variant="tiny" style={{ marginTop: 6 }}>
            Esta é a entrada que o servidor fechou. As demais continuam aguardando; a ordem não
            escolhe vencedor.
          </Txt>
          {matchedEntry.lobby ? (
            <Btn
              tone="primary"
              onPress={() =>
                matchedEntry.lobby &&
                nav.replace('lobby-found', {
                  lobbyId: matchedEntry.lobby.id,
                  mode: matchedEntry.mode,
                })
              }
            >
              Ver partida
            </Btn>
          ) : (
            <Txt variant="tiny">Preparando o lobby da partida…</Txt>
          )}
        </Card>
      ) : null}
      <Card>
        <Row between>
          <Txt variant="h3">
            {queue.length} {queue.length === 1 ? 'busca ativa' : 'buscas ativas'}
          </Txt>
          {queueReconnecting ? <Badge>reconectando</Badge> : <Badge>atualizado</Badge>}
        </Row>
        {queue.length === 0 ? (
          <Txt variant="tiny" style={{ marginTop: 8 }}>
            Nenhuma entrada aguardando. A partida encontrada acima é a única pendência.
          </Txt>
        ) : (
          <View style={{ marginTop: 10, gap: 12 }}>
            {grouped.map((group) => (
              <View key={group.mode} style={{ gap: 8 }}>
                {modeCount > 1 ? <Txt variant="label">{modeLabel(group.mode)}</Txt> : null}
                {group.entries.map(renderEntry)}
              </View>
            ))}
          </View>
        )}
        <Txt variant="tiny" style={{ marginTop: 10 }}>
          {oldest ? `Mais antiga: ${elapsed(oldest, now)}` : 'Sem entradas aguardando.'}
          {profile?.region?.city ? ` · ${profile.region.city}` : ''}
        </Txt>
      </Card>
      <Notice icon="clock">
        Não prometemos um tempo de espera. Uma combinação pode encontrar partida antes das outras; o
        servidor decide e a tela apenas reflete.
      </Notice>
      {queueNotice ? (
        <Notice tone="orange" icon="alert">
          {queueNotice}
        </Notice>
      ) : null}
      {error ? (
        <Notice tone="orange" icon="alert">
          {error}
        </Notice>
      ) : null}
      <Btn tone="primary" onPress={() => nav.go('queue', { from: 'queue-search' })}>
        Alterar busca
      </Btn>
      {confirming ? (
        <Card tone="flat">
          <Txt variant="h3">
            Cancelar as {cancelTarget} {cancelTarget === 1 ? 'busca' : 'buscas'}?
          </Txt>
          <Txt variant="tiny" style={{ marginTop: 6 }}>
            As buscas que ainda aguardam serão canceladas no servidor. Se já há partida encontrada,
            ela não é cancelada aqui. Se a rede falhar, nada é removido da tela.
          </Txt>
          <BtnRow>
            <Btn tone="ghost" onPress={() => setConfirming(false)} disabled={busy}>
              Manter
            </Btn>
            <Btn tone="danger" onPress={cancel} disabled={busy}>
              {busy ? 'Cancelando…' : 'Cancelar tudo'}
            </Btn>
          </BtnRow>
        </Card>
      ) : (
        <Btn tone="ghost" onPress={() => setConfirming(true)} disabled={busy || queue.length === 0}>
          Cancelar todas as buscas
        </Btn>
      )}
      {queueNotice || error ? (
        <Btn small tone="ghost" onPress={() => (queueNotice ? clearQueueNotice() : reload())}>
          {queueNotice ? 'Dispensar aviso' : 'Reler fila'}
        </Btn>
      ) : null}
      <Card tone="flat">
        <Row between>
          <Txt variant="tiny">Enquanto isso</Txt>
          <Btn small tone="ghost" onPress={() => nav.back()}>
            Voltar
          </Btn>
        </Row>
      </Card>
    </Page>
  );
}
