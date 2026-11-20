import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AccessibilityInfo, Animated, View } from 'react-native';

import { describeApiError, ApiError } from '../api/client';
import type { Sport } from '../api/types';
import { useApp } from '../state/app';
import { useNav, useTheme } from '../state/context';
import type { QueueMode } from '../state/queueIntent';
import {
  QUEUE_MODES,
  buildSelection,
  entryMode,
  formatLabelFromCatalog,
  modeLabel,
  oldestCreatedAt,
  queueCourtPreference,
  queueFailureMessage,
  selectionError,
  selectionFromEntries,
  selectionProductCount,
} from '../state/queueState';
import { useActiveInterval } from '../state/useActiveInterval';
import { divisionLabel, elapsed, timeOnly, WEEKDAY_NAMES } from '../ui/datetime';
import { Appear } from '../ui/Appear';
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
  Txt,
} from '../ui/kit';
import { duration, easing, motionDuration, useReducedMotion } from '../ui/motion';
import { PulseDot } from '../ui/PulseDot';
import { Text } from '../ui/text';

function formatName(catalog: readonly Sport[], formatId: string): string {
  return formatLabelFromCatalog(catalog, formatId);
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
    session,
    queue,
    matchedEntry,
    replaceQueue,
    loadQueue,
    clearQueueNotice,
  } = useApp();
  const initialModes = useMemo<QueueMode[]>(
    () => (nav.params.mode === 'ranked' ? ['ranked'] : ['casual']),
    [nav.params.mode],
  );
  const [modes, setModes] = useState<QueueMode[]>(initialModes);
  const [selected, setSelected] = useState<string[]>([]);
  const [court, setCourt] = useState('Tanto faz');
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [syncing, setSyncing] = useState(() => !!session);
  const [failure, setFailure] = useState<{ code: string; message: string } | null>(null);
  const touched = useRef(false);
  const synced = useRef(false);

  const formats = useMemo(() => catalog.flatMap((sport) => sport.formats), [catalog]);
  const options = formats;
  const shownOptions = useMemo(() => options.map((format) => format.name), [options]);
  const optionById = useMemo(
    () => new Map(options.map((format) => [format.id, format])),
    [options],
  );
  const profileFormatIds = useMemo(
    () => (profile?.sports ?? []).map((sport) => sport.format_id),
    [profile],
  );

  useEffect(() => {
    if (catalog.length > 0) {
      return;
    }
    loadCatalog().catch((cause) => {
      if (__DEV__) {
        console.warn('Falha ao carregar /sports', describeApiError(cause));
      }
    });
  }, [catalog.length, loadCatalog]);

  // Reconcilia com o servidor ao montar; a lista exibida nunca vem de
  // `nav.params` nem da seleção local.
  useEffect(() => {
    if (!session || synced.current) {
      return;
    }
    synced.current = true;
    loadQueue()
      .catch((cause) => {
        if (__DEV__) {
          console.warn('GET /matchmaking/queue falhou', describeApiError(cause));
        }
      })
      .finally(() => setSyncing(false));
  }, [session, loadQueue]);

  useEffect(() => {
    if (touched.current) {
      return;
    }
    if (queue.length > 0) {
      const fromQueue = selectionFromEntries(queue);
      // A seleção local só adota o servidor enquanto o usuário não mexeu.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSelected(fromQueue.formats.filter((id) => optionById.has(id)));
      setModes(fromQueue.modes.length > 0 ? fromQueue.modes : initialModes);
      return;
    }
    setSelected((current) => {
      if (current.length > 0) {
        return current;
      }
      const fromProfile = profileFormatIds.filter((id) => optionById.has(id));
      if (fromProfile.length > 0) {
        return fromProfile;
      }
      if (primaryFormatId && optionById.has(primaryFormatId)) {
        return [primaryFormatId];
      }
      return options.length > 0 ? [options[0].id] : [];
    });
  }, [initialModes, optionById, options, primaryFormatId, profileFormatIds, queue]);

  const selectedFormatId = selected[0] ?? primaryFormatId ?? options[0]?.id ?? null;
  const rating = selectedFormatId ? ratings[selectedFormatId] : undefined;
  const ratingsRef = useRef(ratings);
  const requestedRatings = useRef(new Set<string>());

  useEffect(() => {
    ratingsRef.current = ratings;
  }, [ratings]);

  useEffect(() => {
    if (!selectedFormatId) {
      return;
    }
    if (ratingsRef.current[selectedFormatId] || requestedRatings.current.has(selectedFormatId)) {
      return;
    }
    requestedRatings.current.add(selectedFormatId);
    loadRating(selectedFormatId).catch(() => {
      requestedRatings.current.delete(selectedFormatId);
    });
  }, [selectedFormatId, loadRating]);

  const windows = profile?.availability ?? [];
  const firstWindow = windows[0];
  const availabilityTitle = firstWindow
    ? `${WEEKDAY_NAMES[firstWindow.weekday - 1]} · ${firstWindow.start_time.slice(0, 5)}–${firstWindow.end_time.slice(0, 5)}`
    : 'Nenhum horário cadastrado';
  const availabilitySub =
    windows.length > 0
      ? `${windows.length} ${windows.length === 1 ? 'janela' : 'janelas'} na semana`
      : 'Adicione seus horários';
  const regionTitle = profile?.region?.city ?? 'Definir região';
  const regionSub = profile?.region
    ? `raio de ${profile.region.radius_km} km · GPS aproximado`
    : 'sem região definida';

  const toggleFormat = useCallback((formatId: string) => {
    touched.current = true;
    setSelected((current) =>
      current.includes(formatId)
        ? current.length > 1
          ? current.filter((value) => value !== formatId)
          : current
        : [...current, formatId],
    );
  }, []);

  const toggleMode = useCallback((mode: QueueMode) => {
    touched.current = true;
    setModes((current) =>
      current.includes(mode)
        ? current.length > 1
          ? current.filter((value) => value !== mode)
          : current
        : [...current, mode],
    );
  }, []);

  const selection = useMemo(() => buildSelection(selected, modes), [modes, selected]);
  const count = selectionProductCount(selection);
  const hasConfirmed = queue.length > 0 || matchedEntry !== null;
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
      );
      if (result.ok) {
        touched.current = false;
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
  }, [clearQueueNotice, court, hasConfirmed, nav, replaceQueue, selection, session]);

  return (
    <Page title="Buscar partida">
      {syncing ? (
        <Notice icon="clock">Sincronizando suas buscas ativas com o servidor…</Notice>
      ) : null}
      <Card tone="flat">
        <Row between>
          <Txt variant="h3">Modos</Txt>
          <Txt variant="tiny">marque um ou os dois</Txt>
        </Row>
        <ChipRow style={{ marginTop: 8 }}>
          {QUEUE_MODES.map((mode) => (
            <Chip key={mode} on={modes.includes(mode)} onPress={() => toggleMode(mode)}>
              {modeLabel(mode)}
            </Chip>
          ))}
        </ChipRow>
        <Txt variant="tiny" style={{ marginTop: 8 }}>
          Cada modo vira uma busca separada. O servidor decide as partidas; a ordem não é
          preferência.
        </Txt>
      </Card>
      {modes.includes('ranked') ? (
        <Card tone="blue">
          <Row between>
            <View style={{ flex: 1, minWidth: 0 }}>
              <Txt variant="label">Sua divisão</Txt>
              <Txt variant="h2" style={{ marginTop: 3 }}>
                {rating?.provisional ? 'Provisório' : rating ? divisionLabel(rating.division) : '—'}
              </Txt>
            </View>
            <Badge>temporada 2026-Q4</Badge>
          </Row>
          <Txt variant="tiny" style={{ marginTop: 8 }}>
            A divisão é recalculada na virada da temporada.
          </Txt>
        </Card>
      ) : (
        <Card tone="green">
          <Row between>
            <View style={{ flex: 1, minWidth: 0 }}>
              <Txt variant="label">Modo</Txt>
              <Txt variant="h2" style={{ marginTop: 3 }}>
                Casual
              </Txt>
            </View>
            <Badge tone="green">sem divisão</Badge>
          </Row>
          <Txt variant="tiny" style={{ marginTop: 8 }}>
            Partida para jogar e conhecer gente. Resultado não altera sua divisão.
          </Txt>
        </Card>
      )}
      <Card>
        <Row between>
          <Txt variant="h3">Esportes</Txt>
          <Txt variant="tiny">{shownOptions.length} no catálogo</Txt>
        </Row>
        {options.length === 0 ? (
          <Txt variant="tiny" style={{ marginTop: 8 }}>
            Catálogo de formatos indisponível. Tente novamente em instantes.
          </Txt>
        ) : (
          <ChipRow style={{ marginTop: 8 }}>
            {options.map((format) => (
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
      <Card>
        <Txt variant="h3">Preferência de quadra</Txt>
        <ChipRow style={{ marginTop: 8 }}>
          {['Públicas', 'Particulares', 'Tanto faz'].map((item) => (
            <Chip key={item} on={court === item} onPress={() => setCourt(item)}>
              {item}
            </Chip>
          ))}
        </ChipRow>
      </Card>
      <Card>
        <Row between>
          <Txt variant="h3">Região e horário</Txt>
          <Badge>{modes.includes('ranked') ? 'compatível' : 'livre'}</Badge>
        </Row>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 10 }}>
          <View style={{ flex: 1, minWidth: 0 }}>
            <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
              {regionTitle}
            </Text>
            <Text style={{ fontSize: 13, color: palette.muted }}>{regionSub}</Text>
          </View>
          <Btn small tone="ghost" onPress={() => nav.go('region')}>
            Trocar
          </Btn>
        </View>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 8 }}>
          <View style={{ flex: 1, minWidth: 0 }}>
            <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
              {availabilityTitle}
            </Text>
            <Text style={{ fontSize: 13, color: palette.muted }}>{availabilitySub}</Text>
          </View>
          <Btn small tone="ghost" onPress={() => nav.go('availability')}>
            Editar
          </Btn>
        </View>
      </Card>
      <Card tone="flat">
        <Row between>
          <View style={{ flex: 1, minWidth: 0 }}>
            <Txt variant="label">Custo estimado</Txt>
            <Text style={{ fontSize: 30, lineHeight: 34, fontWeight: '900', color: palette.ink }}>
              7 <Text style={{ fontSize: 14, fontWeight: '700' }}>ingressos</Text>
            </Text>
          </View>
          <Badge tone="lime">saldo {wallet?.balance ?? 18}</Badge>
        </Row>
        <Txt variant="tiny" style={{ marginTop: 8 }}>
          O valor final aparece na confirmação da vaga.
        </Txt>
      </Card>
      <Card tone="flat">
        <Row between>
          <Txt variant="label">Buscas que serão enviadas</Txt>
          <Badge>{count}</Badge>
        </Row>
        <Text style={{ fontSize: 26, lineHeight: 30, fontWeight: '900', color: palette.ink }}>
          {count} {count === 1 ? 'busca' : 'buscas'}
        </Text>
        <Txt variant="tiny" style={{ marginTop: 4 }}>
          {selection.formats.length} {selection.formats.length === 1 ? 'esporte' : 'esportes'} ×{' '}
          {selection.modes.length} {selection.modes.length === 1 ? 'modo' : 'modos'}. O servidor
          substitui a seleção atual de uma vez; não somamos buscas antigas.
        </Txt>
      </Card>
      {hasConfirmed ? (
        <Animated.View style={{ opacity: listOpacity }}>
          <Card>
            <Row between>
              <Txt variant="h3">Buscas ativas</Txt>
              <Badge>{queue.length}</Badge>
            </Row>
            {matchedEntry ? (
              <View style={{ marginTop: 8 }}>
                <Txt variant="tiny">Partida encontrada</Txt>
                <Text style={{ fontSize: 15, fontWeight: '800', color: palette.ink }}>
                  {formatName(catalog, matchedEntry.format_id)} ·{' '}
                  {modeLabel(entryMode(matchedEntry))}
                </Text>
              </View>
            ) : null}
            {queue.length === 0 ? (
              <Txt variant="tiny" style={{ marginTop: 8 }}>
                Nenhuma entrada aguardando no servidor.
              </Txt>
            ) : (
              <View style={{ marginTop: 8, gap: 8 }}>
                {queue.map((entry) => (
                  <Row key={entry.id} between>
                    <View style={{ flex: 1, minWidth: 0 }}>
                      <Text
                        numberOfLines={2}
                        style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}
                      >
                        {formatName(catalog, entry.format_id)}
                      </Text>
                      <Text style={{ fontSize: 12, color: palette.muted }}>
                        {modeLabel(entryMode(entry))} · desde {timeOnly(entry.created_at)}
                      </Text>
                    </View>
                  </Row>
                ))}
              </View>
            )}
            <Btn tone="ghost" small onPress={() => nav.go('queue-search')}>
              Acompanhar busca
            </Btn>
          </Card>
        </Animated.View>
      ) : null}
      {modes.includes('ranked') ? (
        <Notice tone="blue" icon="shield">
          Ranqueada exige pelo menos 1 substituto em standby. Fila insuficiente pode virar casual.
        </Notice>
      ) : null}
      {failure ? (
        <Notice tone="orange" icon="alert">
          {failure.message}
        </Notice>
      ) : null}
      {failure?.code === 'region_required' ? (
        <Btn tone="ghost" onPress={() => nav.go('region')}>
          Definir região
        </Btn>
      ) : null}
      {failure?.code === 'sport_profile_required' ? (
        <Btn tone="ghost" onPress={() => nav.go('sports')}>
          Completar modalidades
        </Btn>
      ) : null}
      {failure?.code === 'ranked_restricted' ? (
        <Btn
          tone="ghost"
          onPress={() => {
            touched.current = true;
            setModes(['casual']);
          }}
        >
          Buscar só casual
        </Btn>
      ) : null}
      <Btn
        tone="primary"
        icon="search"
        onPress={submit}
        disabled={busy || options.length === 0 || count === 0}
      >
        {busy
          ? hasConfirmed
            ? 'Atualizando busca…'
            : 'Entrando…'
          : hasConfirmed
            ? 'Atualizar busca'
            : 'Entrar na fila'}
      </Btn>
      {busy ? (
        <Notice icon="clock">
          {hasConfirmed
            ? 'Mantendo a última lista confirmada até o servidor responder.'
            : 'Enviando sua seleção ao servidor. Nada aparece como ativo antes da confirmação.'}
        </Notice>
      ) : null}
      <Btn small tone="ghost" onPress={() => nav.go('queue-empty')}>
        Não encontrei partida
      </Btn>
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
      <Appear>
        <Card>
          <Row between>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              <PulseDot color={palette.limeDeep} size={7} active={queue.length > 0} />
              <Txt variant="h3">
                {queue.length} {queue.length === 1 ? 'busca ativa' : 'buscas ativas'}
              </Txt>
            </View>
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
          <Txt variant="tiny" style={{ marginTop: 10, fontVariant: ['tabular-nums'] }}>
            {oldest ? `Mais antiga: ${elapsed(oldest, now)}` : 'Sem entradas aguardando.'}
            {profile?.region?.city ? ` · ${profile.region.city}` : ''}
          </Txt>
        </Card>
      </Appear>
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
