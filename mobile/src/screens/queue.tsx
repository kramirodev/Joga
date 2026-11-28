import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AccessibilityInfo, Animated, View } from 'react-native';

import { describeApiError, ApiError } from '../api/client';
import type {
  MyRating,
  QueueCourtPreference,
  QueueEntry,
  QueueLevel,
  QueueMode,
  Sport,
} from '../api/types';
import { useApp } from '../state/app';
import { useNav, useTheme } from '../state/context';
import {
  QUEUE_COURT_OPTIONS,
  QUEUE_LEVELS,
  QUEUE_MODES,
  buildSelection,
  buildSelectionPayload,
  divergentCourtFormats,
  draftMatchesIntent,
  emptySelection,
  entryMode,
  formatLabelFromCatalog,
  isFormatSelected,
  isQueueLevel,
  levelKey,
  levelLabel,
  modeLabel,
  oldestCreatedAt,
  pruneSelectionToFormats,
  queueContinuity,
  queueCourtPreference,
  queueFailureMessage,
  resolveCasualLevel,
  resolveCourtPreference,
  selectionCount,
  selectionError,
  selectionFromEntries,
  selectionItemsError,
  selectionPairs,
  withCourt,
  withFormatToggled,
  withLevel,
  withModeToggled,
  withoutRanked,
  type QueueSelection,
} from '../state/queueState';
import { useActiveInterval } from '../state/useActiveInterval';
import { courtLabel, divisionLabel, elapsed, timeOnly, WEEKDAY_NAMES } from '../ui/datetime';
import { Appear } from '../ui/Appear';
import {
  Badge,
  Btn,
  BtnRow,
  Card,
  CardHeader,
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
import { duration, easing, motionDuration, useReducedMotion } from '../ui/motion';
import { PulseDot } from '../ui/PulseDot';
import { Text } from '../ui/text';

type QueueStep = 1 | 2;
type QueueView = 'overview' | 'edit';

type QueueDraft = {
  step: QueueStep;
  selection: QueueSelection;
};

/** Formato antigo do rascunho, lido só para migrar a quadra global. */
type LegacyQueueDraft = QueueDraft & { court?: string };

/**
 * Rascunho da seleção ainda não confirmada. Vive só em memória: sair da tela
 * (inclusive pelo back do Android) não descarta a escolha do usuário, mas nada
 * é enviado ao servidor sem o toque em "Confirmar busca".
 */
let queueDraft: QueueDraft | null = null;

/**
 * O rascunho só volta quando ainda tem o que retomar e continua de acordo com
 * a intenção de entrada. Um rascunho de outra modalidade não pode reabrir a
 * busca com o filtro de esporte de uma seleção anterior.
 */
function resumableDraft(draft: LegacyQueueDraft | null, intent: unknown): LegacyQueueDraft | null {
  if (!draft) {
    return null;
  }
  if (draft.step === 2 && draft.selection.formats.length === 0) {
    return null;
  }
  return draftMatchesIntent(draft.selection, intent) ? draft : null;
}

function formatName(catalog: readonly Sport[], formatId: string): string {
  return formatLabelFromCatalog(catalog, formatId);
}

function modesLabel(modes: readonly QueueMode[]): string {
  const selected = QUEUE_MODES.filter((mode) => modes.includes(mode));
  return selected.length > 0 ? selected.map(modeLabel).join(' e ') : 'Escolha ao menos um';
}

function entryLevelDetail(entry: QueueEntry): string {
  return entryMode(entry) === 'casual' && isQueueLevel(entry.level)
    ? ` · ${levelLabel(entry.level)}`
    : '';
}

/** Ranqueada mostra divisão/MMR; nunca nível. */
function rankedDetail(rating: MyRating | undefined): string {
  if (!rating) {
    return 'Definida pelo seu histórico';
  }
  return rating.provisional ? 'Provisória' : divisionLabel(rating.division);
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
  modes,
  level,
  court,
  courtDisabled,
  divergentCourt,
  rating,
  profileReady,
  kept,
  removed,
  onCompleteProfile,
  onModeToggle,
  onLevelChange,
  onCourtChange,
}: {
  formatId: string;
  catalog: readonly Sport[];
  modes: readonly QueueMode[];
  level: QueueLevel;
  court: QueueCourtPreference | undefined;
  courtDisabled: boolean;
  divergentCourt: boolean;
  rating: MyRating | undefined;
  profileReady: boolean | null;
  kept: QueueEntry[];
  removed: QueueEntry[];
  onCompleteProfile: () => void;
  onModeToggle: (mode: QueueMode) => void;
  onLevelChange: (level: QueueLevel) => void;
  onCourtChange: (court: QueueCourtPreference) => void;
}) {
  const casual = modes.includes('casual');
  const ranked = modes.includes('ranked');
  const name = formatName(catalog, formatId);
  return (
    <Card>
      <Txt variant="lead" weight="800">
        {name}
      </Txt>
      <Txt variant="label" style={{ marginTop: 10 }}>
        Modos
      </Txt>
      <ChipRow style={{ marginTop: 8 }}>
        {QUEUE_MODES.map((mode) => (
          <Chip
            key={mode}
            on={modes.includes(mode)}
            accessibilityLabel={`${modeLabel(mode)} em ${name}`}
            onPress={() => onModeToggle(mode)}
          >
            {modeLabel(mode)}
          </Chip>
        ))}
      </ChipRow>
      {ranked ? (
        <View style={{ marginTop: 8, gap: 2 }}>
          <Txt variant="tiny">Ranqueada · {rankedDetail(rating)}</Txt>
          <Txt variant="tiny">A ranqueada usa sua divisão e compatibilidade; não há nível.</Txt>
        </View>
      ) : null}
      {casual ? (
        <View style={{ marginTop: 12, gap: 6 }}>
          <Txt variant="label">Nível no casual</Txt>
          <ChipRow>
            {QUEUE_LEVELS.map((option) => (
              <Chip
                key={option}
                on={level === option}
                accessibilityLabel={`Nível no casual de ${name}: ${levelLabel(option)}`}
                onPress={() => onLevelChange(option)}
              >
                {levelLabel(option)}
              </Chip>
            ))}
          </ChipRow>
        </View>
      ) : null}
      <View style={{ marginTop: 12, gap: 6 }}>
        <Txt variant="label">Quadra</Txt>
        <ChipRow>
          {QUEUE_COURT_OPTIONS.map((option) => (
            <Chip
              key={option}
              on={court === option}
              disabled={courtDisabled}
              accessibilityLabel={`Quadra de ${name}: ${courtLabel(option)}`}
              onPress={() => onCourtChange(option)}
            >
              {courtLabel(option)}
            </Chip>
          ))}
        </ChipRow>
        {divergentCourt ? (
          <Txt variant="tiny">Ao confirmar, as buscas deste esporte usam a mesma quadra.</Txt>
        ) : null}
      </View>
      <View style={{ marginTop: 12, gap: 8 }}>
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
      {profileReady === false ? (
        <TextBtn onPress={onCompleteProfile}>Completar este esporte</TextBtn>
      ) : null}
    </Card>
  );
}

export function QueueScreen() {
  const nav = useNav();
  const { palette } = useTheme();
  const {
    catalog,
    profile,
    wallet,
    ratings,
    primaryFormatId,
    loadRating,
    loadCatalog,
    loadProfile,
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
  // tela sem virar fonte de verdade do servidor. Rascunho de outra intenção
  // (ou vazio no passo 2) é descartado para não repetir a seleção anterior.
  const [mountDraft] = useState<LegacyQueueDraft | null>(() => {
    const stored = queueDraft as LegacyQueueDraft | null;
    // Quem chega pela busca ativa edita a fila confirmada, não um rascunho
    // antigo: a fila vence a seleção anterior (mesma regra do 2A).
    const resumed =
      nav.params.from === 'queue-search' && queue.length > 0
        ? null
        : resumableDraft(stored, nav.params.mode);
    if (stored && !resumed) {
      queueDraft = null;
    }
    return resumed;
  });
  const legacyCourt = mountDraft?.court ? queueCourtPreference(mountDraft.court) : undefined;
  const [view, setView] = useState<QueueView>(() =>
    mountDraft || nav.params.from === 'queue-search' ? 'edit' : 'overview',
  );
  const [step, setStep] = useState<QueueStep>(() => mountDraft?.step ?? 1);
  // A seleção exibida é sempre podada pelo catálogo atual; um esporte que
  // saiu de `/sports` não volta como chip invisível nem chega ao `PUT`.
  const [rawSelection, setSelection] = useState<QueueSelection>(
    () => mountDraft?.selection ?? emptySelection(),
  );
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [syncing, setSyncing] = useState(() => !!session);
  const [syncError, setSyncError] = useState(false);
  const [profileFailed, setProfileFailed] = useState(false);
  const [profileTick, setProfileTick] = useState(0);
  const [catalogLoading, setCatalogLoading] = useState(() => catalog.length === 0);
  const [failure, setFailure] = useState<{ code: string; message: string } | null>(null);
  const [now, setNow] = useState(() => new Date());
  const touched = useRef(!!mountDraft);
  const synced = useRef(false);

  const formats = useMemo(() => catalog.flatMap((sport) => sport.formats), [catalog]);
  const optionById = useMemo(
    () => new Map(formats.map((format) => [format.id, format])),
    [formats],
  );
  const catalogFormatIds = useMemo(() => new Set(optionById.keys()), [optionById]);
  const selection = useMemo(
    () => pruneSelectionToFormats(rawSelection, catalogFormatIds),
    [catalogFormatIds, rawSelection],
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

  // Perfil é a fonte do default da quadra. Se ainda não chegou, tenta de novo
  // aqui; falha vira aviso com retry, nunca `ANY` silencioso.
  useEffect(() => {
    if (profile || !session) {
      return;
    }
    let active = true;
    loadProfile()
      .then(() => {
        if (active) {
          setProfileFailed(false);
        }
      })
      .catch(() => {
        if (active) {
          setProfileFailed(true);
        }
      });
    return () => {
      active = false;
    };
  }, [loadProfile, profile, profileTick, session]);

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
      setSelection(
        buildSelection(
          fromQueue.formats.filter((id) => optionById.has(id)),
          fromQueue.byFormat,
        ),
      );
      return;
    }
    setSelection((current) => {
      if (current.formats.length > 0) {
        return current;
      }
      if (primaryFormatId && optionById.has(primaryFormatId)) {
        return buildSelection([primaryFormatId], {
          [primaryFormatId]: { modes: initialModes },
        });
      }
      if (formats.length > 0) {
        return buildSelection([formats[0].id], { [formats[0].id]: { modes: initialModes } });
      }
      return current;
    });
  }, [formats, initialModes, optionById, primaryFormatId, queue]);

  const count = selectionCount(selection);
  const continuity = useMemo(() => queueContinuity(queue, selection), [queue, selection]);
  const hasConfirmed = queue.length > 0 || matchedEntry !== null;
  const showOverview = view === 'overview' && hasConfirmed && !syncing;
  const modesFor = useCallback(
    (formatId: string): QueueMode[] => selection.byFormat[formatId]?.modes ?? [],
    [selection],
  );
  const rankedFormatIds = useMemo(
    () =>
      selection.formats.filter((formatId) =>
        (selection.byFormat[formatId]?.modes ?? []).includes('ranked'),
      ),
    [selection],
  );

  const profileLevelFor = useCallback(
    (formatId: string) => profile?.sports.find((sport) => sport.format_id === formatId)?.level,
    [profile],
  );

  // Default da quadra: escolha local → entrada ativa → perfil do formato →
  // rascunho global antigo → ANY. `ANY` do perfil não é sobrescrito.
  const courtFor = useCallback(
    (formatId: string): QueueCourtPreference | undefined => {
      const entry = queue.find((item) => item.format_id === formatId);
      const profileCourt = profile?.sports.find(
        (sport) => sport.format_id === formatId,
      )?.court_preference;
      return resolveCourtPreference(
        selection.byFormat[formatId]?.court,
        entry?.court_preference,
        profileCourt,
        legacyCourt,
      );
    },
    [legacyCourt, profile, queue, selection.byFormat],
  );

  // Default do nível casual: escolha local → entrada confirmada no GET →
  // perfil esportivo. Ranqueada não tem nível.
  const defaultLevelFor = useCallback(
    (formatId: string, mode: QueueMode): QueueLevel | undefined => {
      if (mode !== 'casual') {
        return undefined;
      }
      return resolveCasualLevel(
        selection.byFormat[formatId]?.level,
        serverLevels[levelKey(formatId, 'casual')],
        profileLevelFor(formatId),
      );
    },
    [profileLevelFor, selection.byFormat, serverLevels],
  );

  // Revisão: um par por linha; casual mostra nível, ranqueada mostra divisão.
  const reviewRows = useMemo(
    () =>
      selectionPairs(selection).map(({ formatId, mode }) => ({
        formatId,
        mode,
        level: mode === 'casual' ? (defaultLevelFor(formatId, mode) ?? 'intermediate') : null,
        ranked: mode === 'ranked' ? rankedDetail(ratings[formatId]) : null,
        court: courtFor(formatId),
      })),
    [courtFor, defaultLevelFor, ratings, selection],
  );
  const divergentCourts = useMemo(() => new Set(divergentCourtFormats(queue)), [queue]);
  const profileBlocked =
    profile === null || selection.formats.some((formatId) => !profileFormatIds.includes(formatId));
  // Custo por seleção (Prompt 8 A16–A19 superado): privado mantém o card,
  // público vira "Grátis" sem número, mistura/ANY não mostra número.
  const allPrivate =
    selection.formats.length > 0 &&
    selection.formats.every((formatId) => courtFor(formatId) === 'PRIVATE_ONLY');
  const allPublic =
    selection.formats.length > 0 &&
    selection.formats.every((formatId) => courtFor(formatId) === 'PUBLIC_ONLY');

  // Mantém o rascunho enquanto o usuário está no formulário. O servidor só é
  // alterado no `PUT` de confirmação.
  useEffect(() => {
    if (view !== 'edit') {
      return;
    }
    queueDraft = { step, selection };
  }, [selection, step, view]);

  const ratingsRef = useRef(ratings);
  const requestedRatings = useRef(new Set<string>());

  useEffect(() => {
    ratingsRef.current = ratings;
  }, [ratings]);

  // Ranqueada exibe a divisão de cada esporte; buscamos o rating por formato.
  useEffect(() => {
    for (const formatId of rankedFormatIds) {
      if (ratingsRef.current[formatId] || requestedRatings.current.has(formatId)) {
        continue;
      }
      requestedRatings.current.add(formatId);
      loadRating(formatId).catch(() => {
        requestedRatings.current.delete(formatId);
      });
    }
  }, [loadRating, rankedFormatIds]);

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
      setSelection((current) => withFormatToggled(current, formatId));
    },
    [markTouched],
  );

  const toggleMode = useCallback(
    (formatId: string, mode: QueueMode) => {
      markTouched();
      setSelection((current) => withModeToggled(current, formatId, mode));
    },
    [markTouched],
  );

  const chooseCourt = useCallback(
    (formatId: string, value: QueueCourtPreference) => {
      markTouched();
      setSelection((current) => withCourt(current, formatId, value));
    },
    [markTouched],
  );

  const changeLevel = useCallback(
    (formatId: string, level: QueueLevel) => {
      markTouched();
      // Só casual tem nível; desmarcar/remarcar o modo preserva a escolha.
      setSelection((current) => withLevel(current, formatId, level));
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
      setSelection(
        buildSelection(
          fromQueue.formats.filter((id) => optionById.has(id)),
          fromQueue.byFormat,
        ),
      );
    }
  }, [optionById, queue]);

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

  const reduceMotion = useReducedMotion();
  const [listOpacity] = useState(() => new Animated.Value(1));
  const confirmedSignature = useMemo(
    () => `${queue.map((entry) => entry.id).join('|')}|${matchedEntry?.id ?? ''}`,
    [matchedEntry?.id, queue],
  );
  const signatureRef = useRef(confirmedSignature);

  // A lista confirmada só muda depois do 2xx do PUT ou de um GET. Durante a
  // chamada ela permanece visível e esmaecida; ao confirmar, volta em 180 ms.
  useEffect(() => {
    const changed = signatureRef.current !== confirmedSignature;
    signatureRef.current = confirmedSignature;
    if (changed && !busy) {
      listOpacity.setValue(0.6);
    }
    const animation = Animated.timing(listOpacity, {
      toValue: busy ? 0.55 : 1,
      duration: motionDuration(duration.base, reduceMotion),
      easing: easing.standard,
      useNativeDriver: true,
    });
    animation.start();
    return () => animation.stop();
  }, [busy, confirmedSignature, listOpacity, reduceMotion]);

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
    // Um único payload explícito: casual leva nível; ranqueada omite a chave.
    // A quadra vai em cada item; o global legado não é enviado.
    const payload = buildSelectionPayload(selection, defaultLevelFor, courtFor);
    const payloadProblem = selectionItemsError(payload.selections);
    if (payloadProblem) {
      setFailure({ code: 'invalid_selection', message: payloadProblem });
      return;
    }
    busyRef.current = true;
    setBusy(true);
    setFailure(null);
    clearQueueNotice();
    try {
      // Uma única chamada: o servidor substitui todas as entradas de uma vez.
      const result = await replaceQueue(payload);
      if (result.ok) {
        touched.current = false;
        queueDraft = null;
        AccessibilityInfo.announceForAccessibility(
          hasConfirmed ? 'Busca atualizada.' : 'Busca iniciada.',
        );
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
  }, [
    clearQueueNotice,
    courtFor,
    defaultLevelFor,
    hasConfirmed,
    nav,
    replaceQueue,
    selection,
    session,
  ]);

  const oldestQueue = oldestCreatedAt(queue);
  const tick = useCallback(() => setNow(new Date()), []);
  useActiveInterval(tick, 1000, queue.length > 0 && (showOverview || step === 2));
  // Reancora quando a entrada mais antiga muda (GET/PUT) e garante que o
  // cronômetro não fique preso em 00:00 até o próximo tick.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setNow(new Date());
  }, [oldestQueue]);

  const stepOneBack =
    hasConfirmed && !(nav.params.from === 'queue-search' && nav.canGoBack) ? backToOverview : null;

  if (syncing) {
    return (
      <Page title="Buscar partida" sub="Sincronizando suas buscas">
        <LoadingState label="Sincronizando suas buscas…" />
      </Page>
    );
  }

  if (showOverview) {
    return (
      <Page title="Buscar partida" sub="Suas buscas ativas">
        {syncError ? (
          <View style={{ gap: 8 }}>
            <Notice tone="orange" icon="alert">
              Não foi possível reler suas buscas.
            </Notice>
            <TextBtn onPress={() => void reloadQueue()}>Tentar novamente</TextBtn>
          </View>
        ) : null}
        <Animated.View style={{ opacity: listOpacity }}>
          <Card tone="blue">
            <CardHeader
              variant="label"
              icon={<PulseDot color={palette.limeDeep} size={7} active={queue.length > 0} />}
              title="Buscas ativas"
              badge={<Badge>{queue.length}</Badge>}
            />
            <Txt variant="h2" style={{ marginTop: 4 }}>
              {queue.length} {queue.length === 1 ? 'busca ativa' : 'buscas ativas'}
            </Txt>
            {queue.length > 0 ? (
              <View style={{ marginTop: 8, gap: 4 }}>
                {queue.map((entry) => (
                  <Txt key={entry.id} variant="tiny">
                    {formatName(catalog, entry.format_id)} · {modeLabel(entryMode(entry))}
                    {entryLevelDetail(entry)}
                  </Txt>
                ))}
              </View>
            ) : null}
            {oldestQueue ? (
              <Txt variant="tiny" style={{ marginTop: 4, fontVariant: ['tabular-nums'] }}>
                Mais antiga: {elapsed(oldestQueue, now)}
              </Txt>
            ) : null}
            {matchedEntry ? (
              <View style={{ marginTop: 10 }}>
                <Txt variant="label">Partida encontrada</Txt>
                <Txt variant="lead" weight="800">
                  {formatName(catalog, matchedEntry.format_id)} ·{' '}
                  {modeLabel(entryMode(matchedEntry))}
                  {entryLevelDetail(matchedEntry)}
                </Txt>
                <Txt variant="tiny">As outras buscas continuam aguardando.</Txt>
              </View>
            ) : null}
          </Card>
        </Animated.View>
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
  const keptSince = oldestCreatedAt(continuity.kept);

  return (
    <Page title="Buscar partida" sub={sub}>
      {syncError ? (
        <View style={{ gap: 8 }}>
          <Notice tone="orange" icon="alert">
            Não foi possível reler suas buscas.
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
      {profileFailed && profile === null ? (
        <View style={{ gap: 8 }}>
          <Notice tone="orange" icon="alert">
            Não foi possível carregar seu perfil.
          </Notice>
          <TextBtn
            onPress={() => {
              setProfileFailed(false);
              setProfileTick((current) => current + 1);
            }}
          >
            Tentar de novo
          </TextBtn>
        </View>
      ) : null}

      <Appear key={step} trigger={step} style={{ gap: 14 }}>
        {step === 1 ? (
          <>
            <Card>
              <CardHeader
                title="Escolha os esportes"
                badge={<Txt variant="tiny">{formats.length} no catálogo</Txt>}
              />
              {catalogBusy ? (
                <LoadingState label="Carregando esportes…" />
              ) : formats.length === 0 ? (
                <View style={{ gap: 8, marginTop: 8 }}>
                  <Txt variant="tiny">Catálogo indisponível. Tente novamente.</Txt>
                  <TextBtn onPress={() => void retryCatalog()}>Tentar novamente</TextBtn>
                </View>
              ) : (
                <ChipRow style={{ marginTop: 8 }}>
                  {formats.map((format) => (
                    <Chip
                      key={format.id}
                      on={isFormatSelected(selection, format.id)}
                      accessibilityLabel={`${format.name}, ${isFormatSelected(selection, format.id) ? 'selecionado' : 'não selecionado'}`}
                      onPress={() => toggleFormat(format.id)}
                    >
                      {format.name}
                    </Chip>
                  ))}
                </ChipRow>
              )}
            </Card>

            <Card tone="flat">
              <CardHeader variant="label" title="Serão enviadas" badge={<Badge>{count}</Badge>} />
              <Txt variant="num" style={{ marginTop: 4 }}>
                {count} {count === 1 ? 'busca' : 'buscas'}
              </Txt>
              <Txt variant="tiny" style={{ marginTop: 4 }}>
                {selection.formats.length}{' '}
                {selection.formats.length === 1 ? 'esporte selecionado' : 'esportes selecionados'} ·{' '}
                {count} {count === 1 ? 'par real' : 'pares reais'}.
              </Txt>
              {count === 0 ? (
                <Txt variant="tiny" style={{ marginTop: 6 }}>
                  Escolha pelo menos um esporte e um modo para continuar.
                </Txt>
              ) : null}
              {selection.formats.length > 0 ? (
                <View style={{ marginTop: 8, gap: 4 }}>
                  {selection.formats.map((formatId) => (
                    <Txt key={formatId} variant="tiny">
                      {formatName(catalog, formatId)} · {modesLabel(modesFor(formatId))}
                    </Txt>
                  ))}
                </View>
              ) : null}
              {hasConfirmed && continuity.kept.length > 0 ? (
                <Txt variant="tiny" style={{ marginTop: 6 }}>
                  {continuity.kept.length}{' '}
                  {continuity.kept.length === 1
                    ? 'busca ativa continua'
                    : 'buscas ativas continuam'}{' '}
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
                O horário vale para todos. A quadra pode mudar a cada esporte.
              </Txt>
            </Card>

            {matchedEntry ? (
              <Appear>
                <Card tone="blue">
                  <CardHeader
                    variant="label"
                    title="Partida encontrada"
                    badge={<Badge>enquanto você ajustava</Badge>}
                  />
                  <Txt variant="lead" weight="800">
                    {formatName(catalog, matchedEntry.format_id)} ·{' '}
                    {modeLabel(entryMode(matchedEntry))}
                    {entryLevelDetail(matchedEntry)}
                  </Txt>
                  <Txt variant="tiny">As outras buscas continuam aguardando.</Txt>
                  <TextBtn onPress={() => nav.go('queue-search')}>Ver partida</TextBtn>
                </Card>
              </Appear>
            ) : null}

            {selection.formats.map((formatId) => (
              <SportConfigCard
                key={formatId}
                formatId={formatId}
                catalog={catalog}
                modes={modesFor(formatId)}
                level={defaultLevelFor(formatId, 'casual') ?? 'intermediate'}
                court={courtFor(formatId)}
                courtDisabled={profile === null || !profileFormatIds.includes(formatId)}
                divergentCourt={divergentCourts.has(formatId)}
                rating={ratings[formatId]}
                profileReady={profile ? profileFormatIds.includes(formatId) : null}
                kept={continuity.kept.filter((entry) => entry.format_id === formatId)}
                removed={continuity.removed.filter((entry) => entry.format_id === formatId)}
                onCompleteProfile={() => nav.go('sports')}
                onModeToggle={(mode) => toggleMode(formatId, mode)}
                onLevelChange={(level) => changeLevel(formatId, level)}
                onCourtChange={(court) => chooseCourt(formatId, court)}
              />
            ))}

            <Card>
              <CardHeader title="Horário de disponibilidade" badge={<Badge>para todos</Badge>} />
              <Txt variant="lead" weight="800" style={{ marginTop: 8 }}>
                {availabilityTitle}
              </Txt>
              <Txt variant="tiny">{availabilitySub}</Txt>
              <TextBtn onPress={() => nav.go('availability')}>
                {windows.length > 0 ? 'Editar horários' : 'Adicionar horários'}
              </TextBtn>
            </Card>

            <Card>
              <CardHeader
                title="Região"
                badge={
                  <Badge>{profile?.region ? `${profile.region.radius_km} km` : 'definir'}</Badge>
                }
              />
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

            {allPrivate ? (
              <Card tone="flat">
                <Row between>
                  <View style={{ flex: 1, minWidth: 0 }}>
                    <Txt variant="label">Custo estimado</Txt>
                    <Txt variant="num" style={{ marginTop: 4 }}>
                      7 ingressos
                    </Txt>
                  </View>
                  <Badge tone="lime">
                    {wallet ? `saldo ${wallet.balance}` : 'saldo indisponível'}
                  </Badge>
                </Row>
                <Txt variant="tiny">O valor final aparece na confirmação da vaga.</Txt>
              </Card>
            ) : allPublic ? (
              <Card tone="flat">
                <CardHeader
                  variant="label"
                  title="Quadra"
                  badge={<Badge tone="green">Grátis</Badge>}
                />
                <Txt variant="tiny" style={{ marginTop: 4 }}>
                  Quadra pública não consome ingressos.
                </Txt>
              </Card>
            ) : (
              <Card tone="flat">
                <Txt variant="label">Custo</Txt>
                <Txt variant="tiny" style={{ marginTop: 4 }}>
                  Pode ser grátis em quadra pública. O custo só aparece se a partida for em quadra
                  particular.
                </Txt>
              </Card>
            )}

            <Animated.View style={{ opacity: listOpacity }}>
              <Card tone="flat">
                <CardHeader variant="label" title="Revisão" badge={<Badge>{count}</Badge>} />
                <Txt variant="h2" style={{ marginTop: 4 }}>
                  {count} {count === 1 ? 'busca' : 'buscas'}
                </Txt>
                {reviewRows.length === 0 ? (
                  <Txt variant="tiny" style={{ marginTop: 6 }}>
                    Escolha pelo menos um esporte e um modo para continuar.
                  </Txt>
                ) : (
                  <View style={{ marginTop: 10, gap: 8 }}>
                    {reviewRows.map((row) => (
                      <Txt
                        key={`${row.formatId}:${row.mode}`}
                        variant="sub"
                        style={{ flexShrink: 1 }}
                      >
                        {formatName(catalog, row.formatId)} · {modeLabel(row.mode)} ·{' '}
                        {row.mode === 'ranked'
                          ? row.ranked
                          : row.level
                            ? levelLabel(row.level)
                            : 'Nível a definir'}{' '}
                        · {row.court ? courtLabel(row.court) : 'Quadra a definir'}
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
                    {keptSince ? ` Desde ${timeOnly(keptSince)}.` : ''}
                  </Txt>
                ) : null}
                {keptSince ? (
                  <Txt variant="tiny" style={{ marginTop: 4, fontVariant: ['tabular-nums'] }}>
                    Mais antiga: {elapsed(keptSince, now)}
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
            </Animated.View>

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
                      setSelection((current) => withoutRanked(current));
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
              disabled={busy || count === 0 || selection.formats.length === 0 || profileBlocked}
            >
              {busy
                ? hasConfirmed
                  ? 'Atualizando busca…'
                  : 'Entrando…'
                : hasConfirmed
                  ? 'Atualizar busca'
                  : 'Confirmar busca'}
            </Btn>
            <TextBtn onPress={() => setStep(1)}>Voltar</TextBtn>
          </>
        )}
      </Appear>
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
  const tick = useCallback(() => setNow(new Date()), []);
  useActiveInterval(tick, 1000, queue.length > 0);
  // Reancora o relógio quando a entrada mais antiga muda (entrou, saiu, ou o
  // GET trouxe `created_at` novo).
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setNow(new Date());
  }, [oldest]);

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
    AccessibilityInfo.announceForAccessibility('Partida encontrada.');
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
      AccessibilityInfo.announceForAccessibility('Buscas canceladas.');
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
      <Text
        style={{
          fontSize: 15,
          fontWeight: '800',
          color: palette.ink,
          fontVariant: ['tabular-nums'],
        }}
      >
        {elapsed(entry.created_at, now)}
      </Text>
    </Row>
  );

  if (queue.length === 0 && !matchedEntry) {
    if (syncing) {
      return (
        <Page title="Buscas ativas">
          <LoadingState label="Sincronizando suas buscas…" />
        </Page>
      );
    }
    return (
      <Page title="Buscas ativas">
        <EmptyState
          title="Nenhuma busca ativa"
          text="Nenhuma busca aguardando. Monte uma nova seleção para procurar partida."
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
        <Appear>
          <Card tone="blue">
            <CardHeader
              variant="label"
              title="Partida encontrada"
              badge={<Badge>encontrada</Badge>}
            />
            <Text
              numberOfLines={2}
              style={{ fontSize: 20, lineHeight: 24, fontWeight: '900', color: palette.ink }}
            >
              {formatName(catalog, matchedEntry.format_id)} · {modeLabel(entryMode(matchedEntry))}
            </Text>
            <Txt variant="tiny" style={{ marginTop: 6 }}>
              As outras buscas continuam aguardando.
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
        </Appear>
      ) : null}
      <Appear>
        <Card>
          <CardHeader
            icon={<PulseDot color={palette.limeDeep} size={7} active={queue.length > 0} />}
            title={`${queue.length} ${queue.length === 1 ? 'busca ativa' : 'buscas ativas'}`}
            badge={queueReconnecting ? <Badge>reconectando</Badge> : <Badge>atualizado</Badge>}
          />
          {queue.length === 0 ? (
            <Txt variant="tiny" style={{ marginTop: 8 }}>
              A partida encontrada é a única pendência.
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
          <Txt variant="tiny" style={{ marginTop: 10, fontVariant: ['tabular-nums'] }}>
            {oldest ? `Mais antiga: ${elapsed(oldest, now)}` : 'Sem entradas aguardando.'}
            {profile?.region?.city ? ` · ${profile.region.city}` : ''}
          </Txt>
        </Card>
      </Appear>
      <Notice icon="clock">
        Não prometemos um tempo de espera — pode fechar o aplicativo ou voltar.
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
            As buscas ainda aguardando serão canceladas. A partida encontrada não é cancelada aqui.
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
      <Btn small tone="ghost" onPress={() => nav.back()}>
        Voltar
      </Btn>
    </Page>
  );
}
