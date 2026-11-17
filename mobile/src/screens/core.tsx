import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { KeyboardAvoidingView, Platform, View, useWindowDimensions } from 'react-native';
import * as Location from 'expo-location';

import { api, ApiError } from '../api/client';
import { subscribeLobby, subscribeRealtime } from '../api/realtime';
import type { MatchSummary } from '../api/types';
import { useApp } from '../state/app';
import { useNav, useTheme } from '../state/context';
import { Avatar } from '../ui/Avatar';
import { AddWindowSheet } from '../ui/AddWindowSheet';
import {
  Badge,
  Btn,
  BtnRow,
  Card,
  CardList,
  Chip,
  ChipRow,
  Divider,
  EmptyState,
  Field,
  IconBtn,
  Input,
  Kv,
  ListRow,
  LoadingState,
  Notice,
  Page,
  Photo,
  PhotoCap,
  Pill,
  Progress,
  Range,
  Row,
  Seg,
  SegBtn,
  StateScreen,
  SystemNotice,
  TeamCard,
  TextBtn,
  TimerCard,
  Txt,
} from '../ui/kit';
import {
  countdown,
  courtLabel,
  dateOnly,
  divisionLabel,
  elapsed,
  levelLabel,
  longDate,
  number,
  shortDate,
  timeOnly,
  WEEKDAY_NAMES,
} from '../ui/datetime';
import { Text } from '../ui/text';
import type { ScreenDef } from './types';

function toastError(nav: { toast: (message: string) => void }, error: unknown) {
  if (error instanceof ApiError) {
    const map: Record<string, string> = {
      network_unavailable: 'Não foi possível falar com o servidor.',
      region_required: 'Defina sua região antes de entrar na fila.',
      sport_profile_required: 'Escolha uma modalidade no seu perfil.',
      already_queued: 'Você já está em uma fila.',
      ranked_restricted: 'Ranqueada indisponível no momento.',
      invalid_format: 'Formato indisponível.',
      forbidden: 'Ação não permitida.',
    };
    nav.toast(map[error.code] ?? 'Não foi possível concluir a ação.');
  } else {
    nav.toast('Não foi possível concluir a ação.');
  }
}

function Home() {
  const nav = useNav();
  const { palette } = useTheme();
  const {
    profile,
    onboarding,
    wallet,
    progress,
    track,
    matches,
    missions,
    hydrated,
    session,
    unreadNotifications,
  } = useApp();
  const [now] = useState(() => Date.now());
  const name = profile?.display_name ?? onboarding.displayName ?? 'Jogador';
  const hour = new Date(now).getHours();
  const greeting = hour < 12 ? 'Bom dia' : hour < 18 ? 'Boa tarde' : 'Boa noite';
  const nextMatch = matches.find(
    (match) => !['CANCELLED', 'EXPIRED', 'FINALIZED', 'VOIDED'].includes(match.state),
  );
  const start = nextMatch ? new Date(nextMatch.scheduled_start_at) : null;
  const level = progress?.level ?? 0;
  const tier = progress?.tier ?? 'Bronze';
  const xp = progress?.xp_total ?? 0;
  const maxLevelXp = track?.levels[track.levels.length - 1]?.xp_required ?? 4500;
  const remainingToMax = Math.max(0, maxLevelXp - xp);
  const percent = Math.min(100, Math.round((xp / Math.max(1, maxLevelXp)) * 100));
  const daysLeft = progress
    ? Math.max(0, Math.ceil((new Date(progress.season.ends_at).getTime() - now) / 86_400_000))
    : 0;
  const mission = missions[0];
  const missionLabel =
    mission?.code === 'play_one'
      ? 'Jogar 1 partida'
      : mission?.code === 'new_venue'
        ? 'Jogar em uma quadra nova'
        : mission?.code === 'on_time_checkin'
          ? 'Check-in até o horário de início'
          : 'Missão da semana';
  if (session && !hydrated) {
    return (
      <Page title={`${greeting}, ${name}`} right="bell" rightGo="notifications">
        <LoadingState label="Buscando sua próxima partida." variant="home" />
      </Page>
    );
  }
  const bellNode = (
    <View>
      <IconBtn icon="bell" label="Notificações" go="notifications" />
      {unreadNotifications > 0 ? (
        <View
          pointerEvents="none"
          style={{
            position: 'absolute',
            top: -3,
            right: -3,
            minWidth: 18,
            height: 18,
            borderRadius: 9,
            paddingHorizontal: 4,
            backgroundColor: palette.lime,
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Text style={{ color: '#F1F3F0', fontSize: 10, fontWeight: '900' }}>
            {unreadNotifications > 9 ? '9+' : unreadNotifications}
          </Text>
        </View>
      ) : null}
    </View>
  );
  return (
    <Page title={`${greeting}, ${name}`} rightNode={bellNode}>
      <Row between style={{ marginTop: -4 }}>
        <Txt variant="tiny">{longDate()}</Txt>
      </Row>
      {nextMatch ? (
        <Card tone="ink" padding={18}>
          <Row between>
            <Badge tone="lime">PRÓXIMA PARTIDA</Badge>
            <Badge>CONFIRMADA</Badge>
          </Row>
          <Text
            style={{
              fontSize: 32,
              lineHeight: 31,
              fontWeight: '900',
              letterSpacing: -1,
              textTransform: 'uppercase',
              color: palette.onInk,
              marginTop: 14,
              marginBottom: 4,
            }}
          >
            {start ? `${shortDate(start)}\n${timeOnly(start)}` : ''}
          </Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 7 }}>
            <Text style={{ color: palette.softOnInk }}>◉</Text>
            <Text style={{ color: palette.softOnInk, fontSize: 13 }}>Futebol 5x5</Text>
          </View>
          <View
            style={{
              flexDirection: 'row',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginTop: 14,
              paddingTop: 12,
              borderTopWidth: 1,
              borderTopColor: palette.lineOnInk,
            }}
          >
            <Txt variant="tiny" color="softOnInk">
              Check-in em {countdown(nextMatch.check_in_opens_at)}
            </Txt>
            <Btn
              tone="ghost"
              small
              block={false}
              onPress={() => nav.go('lobby-detail', { matchId: nextMatch.id })}
            >
              Ver partida
            </Btn>
          </View>
        </Card>
      ) : (
        <Card tone="ink" padding={18}>
          <Row between>
            <Badge tone="lime">PRÓXIMA PARTIDA</Badge>
            <Badge>SEM PARTIDA</Badge>
          </Row>
          <Txt
            variant="display"
            color="onInk"
            style={{ fontSize: 26, marginTop: 14, marginBottom: 4 }}
          >
            Nenhuma partida confirmada
          </Txt>
          <Txt variant="tiny" color="softOnInk">
            Entre em uma fila para encontrar sua próxima partida.
          </Txt>
          <View style={{ marginTop: 14 }}>
            <Btn tone="ghost" small block={false} onPress={() => nav.go('queue-casual')}>
              Buscar partida
            </Btn>
          </View>
        </Card>
      )}
      <Card onPress={() => nav.go('wallet')}>
        <Row between>
          <View>
            <Txt variant="label">Ingressos</Txt>
            <Txt variant="num" style={{ fontSize: 34, lineHeight: 34 }}>
              {wallet ? wallet.balance : '—'}
            </Txt>
            <Txt variant="tiny">{wallet ? 'disponíveis' : 'saldo indisponível'}</Txt>
          </View>
          <Badge tone="lime">COMPRAR</Badge>
        </Row>
      </Card>
      {mission ? (
        <Card onPress={() => nav.go('missions')}>
          <Row between>
            <Txt variant="label">Missão da semana</Txt>
            <Badge tone="lime">+{mission.xp_reward} XP</Badge>
          </Row>
          <Txt variant="h3" style={{ marginTop: 7, marginBottom: 3 }}>
            {missionLabel}
          </Txt>
          <Txt variant="sub">
            {`${Math.min(mission.progress, mission.target)} de ${mission.target} nesta semana. Volte para resgatar o XP.`}
          </Txt>
          <View style={{ marginTop: 10 }}>
            <Progress value={(mission.progress / Math.max(1, mission.target)) * 100} />
          </View>
        </Card>
      ) : null}
      <Card onPress={() => nav.go('season')}>
        <Row between>
          <Txt variant="label">Temporada {progress?.season.code ?? '2026-Q4'}</Txt>
          <Badge>{`${tier.toUpperCase()} ${level}`}</Badge>
        </Row>
        <Row between style={{ marginTop: 8, marginBottom: 5 }}>
          <Txt variant="h3">{number(xp)} XP</Txt>
          <Txt variant="tiny">faltam {number(remainingToMax)} para o nível 30</Txt>
        </Row>
        <Progress value={percent} tone="orange" />
        <Row between style={{ marginTop: 8 }}>
          <Txt variant="tiny">{daysLeft} dias restantes</Txt>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
            <Txt variant="tiny">Ver trilha</Txt>
            <Text style={{ color: palette.muted }}>›</Text>
          </View>
        </Row>
      </Card>
      <Row between>
        <Txt variant="h3">Explorar</Txt>
        <Txt variant="tiny">Tudo à mão</Txt>
      </Row>
      <CardList>
        {[
          {
            icon: 'pin' as const,
            title: 'Quadras',
            sub: 'Descobrir quadras e reservar',
            go: 'venues',
          },
          {
            icon: 'clan' as const,
            title: 'Clãs',
            sub: 'Seu clã, membros e troféus',
            go: 'clan',
          },
          {
            icon: 'trophy' as const,
            title: 'Ranking',
            sub: 'Sua posição por modalidade',
            go: 'ranking',
          },
          {
            icon: 'wallet' as const,
            title: 'Ingressos',
            sub: 'Ingressos, passe e reembolsos',
            go: 'wallet',
          },
        ].map((item, index, all) => (
          <ListRow key={item.title} last={index === all.length - 1} onPress={() => nav.go(item.go)}>
            <IconBtn icon={item.icon} label={item.title} plain go={item.go} />
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                {item.title}
              </Text>
              <Text style={{ fontSize: 13, color: palette.muted }}>{item.sub}</Text>
            </View>
            <Text style={{ color: palette.muted }}>›</Text>
          </ListRow>
        ))}
      </CardList>
      <Btn tone="primary" icon="search" go="queue-casual">
        Buscar partida
      </Btn>
    </Page>
  );
}

function QueueScreen({ mode }: { mode: 'casual' | 'ranked' }) {
  const nav = useNav();
  const { palette } = useTheme();
  const { catalog, profile, wallet, ratings, primaryFormatId, formatForName, loadRating } =
    useApp();
  const ranked = mode === 'ranked';
  const [selected, setSelected] = useState<string[]>(['Futebol 5x5']);
  const [court, setCourt] = useState('Tanto faz');
  const [busy, setBusy] = useState(false);
  const formats = catalog.flatMap((sport) => sport.formats);
  const options = formats.length
    ? formats.filter((format) =>
        ['futebol', 'vôlei', 'volei'].some((term) => format.name.toLowerCase().includes(term)),
      )
    : [];
  const shownOptions = options.length
    ? options.map((format) => format.name)
    : ['Futebol 5x5', 'Vôlei 6x6'];
  const selectedFormatId =
    formatForName(selected[0] ?? 'Futebol 5x5') ?? primaryFormatId ?? formats[0]?.id ?? null;
  const rating = selectedFormatId ? ratings[selectedFormatId] : undefined;
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

  useEffect(() => {
    if (selectedFormatId && !rating) {
      loadRating(selectedFormatId).catch(() => undefined);
    }
  }, [selectedFormatId, rating, loadRating]);

  const app = useApp();
  const enqueue = async () => {
    if (!app.session) {
      nav.go('queue-search');
      return;
    }
    if (!selectedFormatId) {
      nav.toast('Formato indisponível.');
      return;
    }
    setBusy(true);
    try {
      const preference =
        court === 'Públicas' ? 'PUBLIC_ONLY' : court === 'Particulares' ? 'PRIVATE_ONLY' : 'ANY';
      await api.matchmaking.enqueue(app.session.accessToken, selectedFormatId, mode, preference);
      nav.go('queue-search');
    } catch (error) {
      if (error instanceof ApiError && error.code === 'region_required') {
        nav.go('region');
      } else if (error instanceof ApiError && error.code === 'ranked_restricted') {
        nav.go('queue-restricted');
      } else if (error instanceof ApiError && error.code === 'sport_profile_required') {
        nav.go('sports');
      } else if (error instanceof ApiError && error.code === 'already_queued') {
        nav.go('queue-search');
      } else {
        toastError(nav, error);
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <Page title="Buscar partida">
      <Seg>
        <SegBtn on={!ranked} go="queue-casual">
          Casual
        </SegBtn>
        <SegBtn on={ranked} go="queue-ranked">
          Ranqueada
        </SegBtn>
      </Seg>
      {ranked ? (
        <Card tone="blue">
          <Row between>
            <View>
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
            <View>
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
        <Txt variant="h3">Formato</Txt>
        <ChipRow style={{ marginTop: 8 }}>
          {shownOptions.map((item, index) => (
            <Chip
              key={item}
              on={selected.includes(item)}
              onPress={() =>
                setSelected((current) =>
                  current.includes(item)
                    ? current.length > 1
                      ? current.filter((value) => value !== item)
                      : current
                    : [...current, item],
                )
              }
              icon={index === 0 ? 'bolt' : undefined}
            >
              {item}
            </Chip>
          ))}
        </ChipRow>
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
          <Badge>{ranked ? 'compatível' : 'livre'}</Badge>
        </Row>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 10 }}>
          <IconBtn icon="pin" label="Região" plain />
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
              {regionTitle}
            </Text>
            <Text style={{ fontSize: 13, color: palette.muted }}>{regionSub}</Text>
          </View>
          <TextBtn go="region">Trocar</TextBtn>
        </View>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 8 }}>
          <IconBtn icon="clock" label="Horário" plain />
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
              {availabilityTitle}
            </Text>
            <Text style={{ fontSize: 13, color: palette.muted }}>{availabilitySub}</Text>
          </View>
          <TextBtn go="availability">Editar</TextBtn>
        </View>
      </Card>
      <Card tone="flat">
        <Row between>
          <View>
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
      {ranked ? (
        <Notice tone="blue" icon="shield">
          Ranqueada exige pelo menos 1 substituto em standby. Fila insuficiente pode virar casual.
        </Notice>
      ) : null}
      <Btn tone="primary" icon="search" onPress={enqueue} disabled={busy}>
        {busy ? 'Entrando…' : 'Entrar na fila'}
      </Btn>
      <TextBtn go="queue-empty" muted>
        Ampliar filtros
      </TextBtn>
    </Page>
  );
}

function QueueSearch() {
  const nav = useNav();
  const { palette } = useTheme();
  const { queue, loadQueue, session, profile } = useApp();
  const [now, setNow] = useState(new Date());
  const [busy, setBusy] = useState(false);
  const routed = useRef(false);
  const started = useMemo(() => (queue ? new Date(queue.created_at) : new Date()), [queue]);
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    if (!session) {
      return;
    }
    const timer = setInterval(() => {
      loadQueue()
        .then((entry) => {
          if (entry?.lobby && !routed.current) {
            routed.current = true;
            // replace evita empilhar a mesma tela a cada polling de 5 s.
            nav.replace('lobby-found', { lobbyId: entry.lobby.id, mode: entry.mode });
          }
        })
        .catch(() => undefined);
    }, 5000);
    return () => clearInterval(timer);
  }, [session, loadQueue, nav]);
  const cancel = async () => {
    setBusy(true);
    try {
      if (session) {
        await api.matchmaking.leave(session.accessToken);
      }
      nav.go('home');
    } catch {
      nav.toast('Não foi possível sair da fila.');
    } finally {
      setBusy(false);
    }
  };
  return (
    <Page title="Procurando partida">
      <View style={{ alignItems: 'center', paddingTop: 12, gap: 12 }}>
        <View
          style={{
            width: 72,
            height: 72,
            borderRadius: 36,
            backgroundColor: palette.surface2,
            borderWidth: 1.5,
            borderColor: palette.line,
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Text style={{ fontSize: 30, color: palette.ink }}>⌕</Text>
        </View>
        <Txt variant="h1" align="center">
          Procurando{'\n'}partida
        </Txt>
        <Txt variant="tiny" align="center">
          Futebol 5x5 · casual{profile?.region?.city ? ` · ${profile.region.city}` : ''}
        </Txt>
        <Txt variant="num" style={{ fontSize: 42, lineHeight: 46 }}>
          {elapsed(started, now)}
        </Txt>
        <Txt variant="tiny">tempo real na fila</Txt>
      </View>
      <Notice icon="clock">Não prometemos um tempo de espera. Você pode sair quando quiser.</Notice>
      <Btn tone="ghost" onPress={cancel} disabled={busy}>
        Cancelar busca
      </Btn>
      <Card tone="flat">
        <Row between>
          <Txt variant="tiny">Enquanto isso</Txt>
          <TextBtn go="queue-casual">Ver lobbies em formação</TextBtn>
        </Row>
      </Card>
    </Page>
  );
}

function QueueEmpty() {
  return (
    <Page title="Fila">
      <EmptyState
        title="Nenhuma partida agora"
        text="Não há lobby compatível na sua região e janela. Você pode ampliar o raio, mudar o horário ou entrar na espera."
        actions={
          <>
            <Btn tone="primary" go="queue-search">
              Ampliar para 20 km
            </Btn>
            <Btn tone="ghost" go="availability">
              Mudar horário
            </Btn>
            <Btn tone="ghost" toast="Você entrou na espera no protótipo">
              Entrar na espera
            </Btn>
          </>
        }
      />
      <Notice icon="info">A espera não garante partida e não cobra ingresso.</Notice>
    </Page>
  );
}

function QueueRestricted() {
  return (
    <Page title="Fila ranqueada">
      <StateScreen
        icon="lock"
        title="Ranqueada indisponível por 7 dias"
        text="Dois no-shows em 30 dias acionaram uma restrição temporária. O casual continua liberado."
        actions={
          <>
            <Btn tone="primary" go="queue-casual">
              Jogar casual
            </Btn>
            <Btn tone="ghost" go="support">
              Entender a regra
            </Btn>
          </>
        }
      />
    </Page>
  );
}

function LobbyFound() {
  return (
    <Page title="Partida encontrada">
      <StateScreen
        icon="check"
        title={'Partida\nencontrada'}
        text="10 jogadores compatíveis. Confirme sua participação para o JOGA solicitar a quadra."
      />
      <Card>
        <Kv label="Formato" value="Futebol 5x5" />
        <Kv label="Horário" value="Ter, 17 nov · 20:00" />
        <Kv label="Região" value="Centro · até 8 km" />
        <Kv label="Modo" value="Casual" />
      </Card>
      <Notice tone="blue" icon="clock">
        A quadra ainda não foi acionada.
      </Notice>
      <Btn tone="primary" go="lobby-t1">
        Confirmar participação
      </Btn>
      <Btn tone="ghost" go="lobby-detail">
        Ver detalhes
      </Btn>
    </Page>
  );
}

function teams(match: MatchSummary | null) {
  if (!match?.participants?.length) {
    return null;
  }
  const active = match.participants.filter((item) => !item.is_substitute);
  const a = active.filter((item) => item.team === 1);
  const b = active.filter((item) => item.team === 2);
  return { a, b };
}

function LobbyDetail() {
  const nav = useNav();
  const { palette } = useTheme();
  const { matches, session } = useApp();
  const [match, setMatch] = useState<MatchSummary | null>(null);
  const matchId = typeof nav.params.matchId === 'string' ? nav.params.matchId : null;
  useEffect(() => {
    if (matchId && session) {
      api.matches
        .get(session.accessToken, matchId)
        .then(setMatch)
        .catch(() => undefined);
    }
  }, [matchId, session]);
  const current = match ?? matches.find((item) => item.id === matchId) ?? null;
  const grouped = teams(current);
  const lobbyId = typeof nav.params.lobbyId === 'string' ? nav.params.lobbyId : current?.lobby_id;
  const start = current ? new Date(current.scheduled_start_at) : null;
  const cancel = async () => {
    if (session && current) {
      try {
        await api.matches.decline(session.accessToken, current.id);
        nav.replace('lobby-canceled');
      } catch (error) {
        toastError(nav, error);
      }
    } else {
      nav.toast('Escolha uma partida para cancelar a participação.');
    }
  };
  return (
    <Page title="Futebol 5x5">
      <Card tone="ink">
        <Row between>
          <Badge tone="lime">CONFIRMADA</Badge>
          <Badge>{current?.state === 'PENDING_CONFIRMATION' ? 'PENDENTE' : 'CASUAL'}</Badge>
        </Row>
        <Text
          style={{
            fontSize: 28,
            lineHeight: 27,
            fontWeight: '900',
            letterSpacing: -0.8,
            textTransform: 'uppercase',
            color: palette.onInk,
            marginTop: 10,
            marginBottom: 4,
          }}
        >
          {start ? `${shortDate(start)} · ${timeOnly(start)}` : 'Horário a confirmar'}
        </Text>
        <Txt variant="tiny" color="softOnInk">
          {current?.state ?? 'Partida'} · local definido na reserva
        </Txt>
      </Card>
      <View style={{ flexDirection: 'row', gap: 7 }}>
        <TimerCard label="T1" value="ok" note="participação" tone="done" />
        <TimerCard label="T2" value="ok" note="quadra aceitou" tone="done" />
      </View>
      <Card tone="lime">
        <Row between wrap style={{ rowGap: 8 }}>
          <View style={{ flexGrow: 1, flexShrink: 1, flexBasis: '60%', minWidth: 0 }}>
            <Txt variant="label">Ingressos</Txt>
            <Txt variant="h3">Consumo definido na reserva</Txt>
          </View>
          <Badge tone="lime">CONGELADO</Badge>
        </Row>
      </Card>
      <Row between>
        <Txt variant="h3">Times</Txt>
        <Badge>{current?.participants?.length ?? 10} jogadores</Badge>
      </Row>
      <View style={{ gap: 8 }}>
        {grouped ? (
          <>
            <TeamCard
              name="Time A"
              badge={<Badge>{grouped.a.length}/5</Badge>}
              players={grouped.a.map((item, index) => ({
                name: item.display_name ?? `Jogador ${index + 1}`,
                role: item.level,
                avatar: {
                  skin: '#A6ABB1',
                  hair: '#17191B',
                  shirt: '#62686E',
                  style: ((index % 3) + 1) as 1 | 2 | 3,
                },
              }))}
            />
            <TeamCard
              name="Time B"
              badge={<Badge>{grouped.b.length}/5</Badge>}
              players={grouped.b.map((item, index) => ({
                name: item.display_name ?? `Jogador ${index + 1}`,
                role: item.level,
                avatar: {
                  skin: '#A6ABB1',
                  hair: '#17191B',
                  shirt: '#62686E',
                  style: ((index % 3) + 1) as 1 | 2 | 3,
                },
              }))}
            />
          </>
        ) : (
          <Notice tone="blue" icon="users">
            Os participantes aparecem quando a partida for carregada pelo servidor.
          </Notice>
        )}
      </View>
      <BtnRow>
        <Btn
          tone="primary"
          icon="check"
          onPress={() => nav.go('checkin-pre', { matchId: matchId ?? '' })}
        >
          Check-in
        </Btn>
        <Btn
          tone="ghost"
          onPress={() =>
            nav.go(
              current?.state === 'RESULT_PENDING' || current?.state === 'DISPUTED'
                ? 'result-review'
                : 'report-result',
              { matchId: matchId ?? '' },
            )
          }
        >
          {current?.state === 'RESULT_PENDING' || current?.state === 'DISPUTED'
            ? 'Ver resultado'
            : 'Relatar resultado'}
        </Btn>
      </BtnRow>
      <BtnRow>
        <Btn
          tone="ghost"
          icon="chat"
          onPress={() => nav.go('lobby-chat', { lobbyId: lobbyId ?? '' })}
        >
          Chat
        </Btn>
        <Btn tone="ghost" go="support">
          Suporte
        </Btn>
      </BtnRow>
      <Btn tone="ghost" onPress={() => nav.openModal('cancel', cancel)}>
        Cancelar participação
      </Btn>
    </Page>
  );
}

function LobbyT1() {
  const nav = useNav();
  const { session, matches } = useApp();
  const matchId = typeof nav.params.matchId === 'string' ? nav.params.matchId : matches[0]?.id;
  const match = matches.find((item) => item.id === matchId) ?? null;
  const confirm = async () => {
    if (session && matchId) {
      try {
        await api.matches.confirm(session.accessToken, matchId);
      } catch (error) {
        toastError(nav, error);
        return;
      }
    }
    nav.replace('lobby-detail', { matchId });
  };
  return (
    <Page title="Confirme sua participação">
      <TimerCard
        label="T1 · confirmação de participação"
        value={match ? countdown(match.confirmation_deadline) : '--'}
        note={match ? `até ${timeOnly(match.confirmation_deadline)}` : 'aguardando partida'}
        tone="on"
      />
      <Card>
        <Kv label="Partida" value={match ? `Partida ${match.id.slice(0, 4).toUpperCase()}` : '—'} />
        <Kv
          label="Horário"
          value={
            match
              ? `${shortDate(match.scheduled_start_at)} · ${timeOnly(match.scheduled_start_at)}`
              : '—'
          }
        />
        <Kv label="Local" value="Definido na reserva da quadra" />
        <Kv label="Ingressos" value="Definidos pela faixa e formato" />
      </Card>
      <Notice tone="lime" icon="wallet">
        Ao confirmar, o servidor consome os ingressos da faixa congelada na reserva. O app não
        calcula o preço.
      </Notice>
      <Btn tone="primary" onPress={confirm}>
        Confirmar participação
      </Btn>
      <Btn tone="ghost" go="lobby-canceled">
        Recusar
      </Btn>
    </Page>
  );
}

function LobbyChat() {
  const nav = useNav();
  const { palette } = useTheme();
  const { session, matches } = useApp();
  const lobbyId =
    typeof nav.params.lobbyId === 'string' ? nav.params.lobbyId : matches[0]?.lobby_id;
  const [messages, setMessages] = useState<
    { id: string; sender: string; body: string; time: string; mine: boolean }[]
  >([]);
  const [input, setInput] = useState('');
  const loadMessages = useCallback(async () => {
    if (!lobbyId || !session) {
      return;
    }
    try {
      const result = await api.chat.list(session.accessToken, lobbyId);
      setMessages(
        result.messages.map((message) => ({
          id: message.id,
          sender: message.sender_id === session.userId ? 'Você' : 'Jogador',
          body: message.body,
          time: timeOnly(message.created_at),
          mine: message.sender_id === session.userId,
        })),
      );
    } catch {
      // Mantém o histórico já carregado; o polling/WebSocket tenta de novo.
    }
  }, [lobbyId, session]);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadMessages();
  }, [loadMessages]);
  useEffect(() => {
    if (!lobbyId || !session) {
      return;
    }
    const unsubscribeLobby = subscribeLobby(lobbyId);
    const unsubscribe = subscribeRealtime((event) => {
      if (event.type === 'lobby.message.created') {
        void loadMessages();
      }
    });
    // Fallback de 15 s caso o WebSocket esteja indisponível na rede.
    const timer = setInterval(() => void loadMessages(), 15_000);
    return () => {
      clearInterval(timer);
      unsubscribe();
      unsubscribeLobby();
    };
  }, [lobbyId, session, loadMessages]);
  const visible = messages;
  const send = async () => {
    const body = input.trim();
    if (!body) {
      return;
    }
    if (lobbyId && session) {
      try {
        await api.chat.send(session.accessToken, lobbyId, body);
      } catch (error) {
        toastError(nav, error);
        return;
      }
    }
    setMessages((current) => [
      ...current,
      { id: String(Date.now()), sender: 'Você', body, time: timeOnly(new Date()), mine: true },
    ]);
    setInput('');
  };
  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <Page title="Chat da partida">
        <Card tone="flat" padding={9}>
          <Row between>
            <Txt variant="tiny">Mensagens deste lobby</Txt>
            <Badge tone="green">só participantes</Badge>
          </Row>
        </Card>
        <View style={{ gap: 10 }}>
          {visible.length === 0 ? (
            <Card tone="flat" padding={12}>
              <Txt variant="tiny">Nenhuma mensagem ainda. Comece a conversa.</Txt>
            </Card>
          ) : null}
          {visible.map((message) =>
            message.sender === 'SISTEMA' ? (
              <SystemNotice key={message.id}>{message.body}</SystemNotice>
            ) : (
              <View
                key={message.id}
                style={[
                  {
                    alignSelf: message.mine ? 'flex-end' : 'flex-start',
                    maxWidth: '88%',
                    paddingHorizontal: 12,
                    paddingVertical: 10,
                    borderRadius: 18,
                    borderWidth: 1.5,
                    borderColor: palette.line,
                    backgroundColor: message.mine ? palette.limeSoft : palette.surface,
                  },
                ]}
              >
                <Txt variant="tiny">
                  <Text style={{ fontWeight: '800', color: palette.ink }}>{message.sender}</Text>
                  {message.time ? ` · ${message.time}` : ''}
                </Txt>
                <Text style={{ marginTop: 3, fontSize: 14, color: palette.ink }}>
                  {message.body}
                </Text>
              </View>
            ),
          )}
          <Card tone="flat" padding={10}>
            <Row between>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                <Text style={{ color: palette.muted }}>◉</Text>
                <Txt variant="tiny">O histórico fica disponível para os participantes.</Txt>
              </View>
            </Row>
          </Card>
        </View>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <IconBtn icon="plus" label="Referência" modal="share" />
          <Input
            value={input}
            onChangeText={setInput}
            placeholder="Mensagem para o lobby"
            maxLength={2000}
            style={{ flex: 1 }}
            onSubmitEditing={send}
          />
          <IconBtn icon="send" label="Enviar" ink onPress={send} />
        </View>
        <Row between>
          <Txt variant="tiny">Texto apenas · 1–2.000 caracteres</Txt>
          <TextBtn go="report-message" muted>
            Denunciar
          </TextBtn>
        </Row>
      </Page>
    </KeyboardAvoidingView>
  );
}

function LobbyInvite() {
  const nav = useNav();
  const { palette } = useTheme();
  const { friends, session, loadSocial } = useApp();
  const lobbyId = typeof nav.params.lobbyId === 'string' ? nav.params.lobbyId : null;
  const [selected, setSelected] = useState<string[]>([]);
  const [query, setQuery] = useState('');
  useEffect(() => {
    loadSocial().catch(() => undefined);
  }, [loadSocial]);
  const list = friends
    .filter((friend) =>
      (friend.display_name ?? 'Jogador').toLowerCase().includes(query.trim().toLowerCase()),
    )
    .map((friend) => ({
      id: friend.user_id,
      name: friend.display_name ?? 'Jogador',
      tag: '',
    }));
  const send = async () => {
    if (!lobbyId || !session) {
      nav.toast('Escolha um lobby para enviar convites.');
      return;
    }
    try {
      await Promise.all(
        selected.map((userId) => api.social.inviteToLobby(session.accessToken, lobbyId, userId)),
      );
      nav.toast('Convites enviados.');
      nav.back();
    } catch (error) {
      toastError(nav, error);
    }
  };
  return (
    <Page title="Convidar para a partida">
      <Txt variant="lead">Convide amigos para este lobby. Só quem participa pode entrar.</Txt>
      <Input
        placeholder="Buscar amigo por nome"
        maxLength={60}
        value={query}
        onChangeText={setQuery}
      />
      {list.length === 0 ? (
        <Notice tone="blue" icon="users">
          Nenhum amigo disponível para convidar. A amizade é criada fora deste fluxo.
        </Notice>
      ) : null}
      <CardList>
        {list.map((friend, index) => {
          const checked = selected.includes(friend.id);
          return (
            <ListRow key={friend.id} last={index === list.length - 1}>
              <Avatar size={34} palette={palette} />
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                  {friend.name}{' '}
                  {friend.tag ? (
                    <Text style={{ color: palette.muted, fontWeight: '400' }}>{friend.tag}</Text>
                  ) : null}
                </Text>
                <Text style={{ fontSize: 13, color: palette.muted, marginTop: 2 }}>
                  Amizade aceita
                </Text>
              </View>
              <View
                onTouchEnd={() => {
                  setSelected((current) =>
                    current.includes(friend.id)
                      ? current.filter((value) => value !== friend.id)
                      : [...current, friend.id],
                  );
                }}
                style={{
                  width: 22,
                  height: 22,
                  borderRadius: 3,
                  borderWidth: 2,
                  borderColor: checked ? palette.ink : palette.lineStrong,
                  backgroundColor: checked ? palette.ink : palette.surface,
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                {checked ? <Text style={{ color: palette.onInk, fontSize: 13 }}>✓</Text> : null}
              </View>
            </ListRow>
          );
        })}
      </CardList>
      <Notice tone="blue" icon="info">
        Convite não garante vaga. Aceite respeita lotação, bloqueio e estado do lobby.
      </Notice>
      <Btn tone="primary" onPress={send} disabled={selected.length === 0}>
        Enviar convites
      </Btn>
    </Page>
  );
}

function LobbyInviteReceived() {
  const nav = useNav();
  const { invites, session, loadSocial } = useApp();
  const [busy, setBusy] = useState(false);
  const inviteId = typeof nav.params.inviteId === 'string' ? nav.params.inviteId : null;
  const invite = invites.find((item) => item.id === inviteId) ?? invites[0] ?? null;
  const decide = async (decision: 'accept' | 'decline') => {
    if (!session || !invite || busy) {
      return;
    }
    setBusy(true);
    try {
      if (decision === 'accept') {
        const updated = await api.social.acceptInvite(session.accessToken, invite.id);
        await loadSocial();
        nav.replace('lobby-detail', { lobbyId: updated.lobby_id });
      } else {
        await api.social.declineInvite(session.accessToken, invite.id);
        await loadSocial();
        nav.back();
      }
    } catch (error) {
      toastError(nav, error);
    } finally {
      setBusy(false);
    }
  };
  if (!invite) {
    return (
      <Page title="Convite de partida">
        <EmptyState
          title="Nenhum convite ativo"
          text="Convites de lobby aparecem aqui e nas notificações enquanto não expiram."
          actions={
            <Btn tone="primary" go="notifications">
              Ver notificações
            </Btn>
          }
        />
      </Page>
    );
  }
  return (
    <Page title="Convite de partida">
      <Card>
        <Row between>
          <Badge tone="lime">CONVITE</Badge>
          <Txt variant="tiny">expira em {dateOnly(invite.expires_at)}</Txt>
        </Row>
        <Txt variant="display" style={{ fontSize: 26, marginTop: 14, marginBottom: 4 }}>
          Convite para{'\n'}um lobby
        </Txt>
        <Txt variant="tiny">Remetente: {invite.inviter_id.slice(0, 8)}…</Txt>
      </Card>
      <Card tone="flat">
        <Kv label="Status" value={invite.status} />
        <Kv label="Recebido em" value={dateOnly(invite.created_at)} />
      </Card>
      <Notice tone="blue" icon="info">
        Aceitar não garante vaga até o lobby validar lotação, bloqueio e estado no servidor.
      </Notice>
      <Btn tone="primary" onPress={() => decide('accept')} disabled={busy}>
        {busy ? 'Respondendo…' : 'Aceitar convite'}
      </Btn>
      <Btn tone="ghost" onPress={() => decide('decline')} disabled={busy}>
        Recusar
      </Btn>
    </Page>
  );
}

function LobbyOpen() {
  const nav = useNav();
  const { palette } = useTheme();
  return (
    <Page title="Lobbies abertos">
      <ChipRow>
        <Chip on>Futebol 5x5</Chip>
        <Chip on>Hoje</Chip>
        <Chip>Até 10 km</Chip>
      </ChipRow>
      <Card onPress={() => nav.go('lobby-detail')}>
        <Row between>
          <Badge tone="lime">2 VAGAS</Badge>
          <Txt variant="tiny">20:00</Txt>
        </Row>
        <Txt variant="h2" style={{ marginTop: 6, marginBottom: 2 }}>
          Arena Sul · 5x5
        </Txt>
        <Txt variant="tiny">Centro · 4,2 km · casual · 7 ingressos</Txt>
        <Row between style={{ marginTop: 12 }}>
          <View style={{ flexDirection: 'row' }}>
            <Avatar size={34} style={1} palette={palette} />
            <Avatar size={34} style={2} palette={palette} />
            <Avatar size={34} style={3} palette={palette} />
          </View>
          <Btn tone="primary" small block={false} onPress={() => nav.go('lobby-detail')}>
            Entrar
          </Btn>
        </Row>
      </Card>
      <Card>
        <Row between>
          <Badge>CHEIO</Badge>
          <Txt variant="tiny">21:00</Txt>
        </Row>
        <Txt variant="h2" style={{ marginTop: 6, marginBottom: 2 }}>
          Arena Norte · 5x5
        </Txt>
        <Txt variant="tiny">Zona Norte · 8,1 km · casual · 6 ingressos</Txt>
        <Row between style={{ marginTop: 12 }}>
          <Txt variant="tiny">Fila de espera disponível</Txt>
          <Btn tone="ghost" small block={false} go="lobby-full">
            Esperar
          </Btn>
        </Row>
      </Card>
      <Btn tone="ghost" icon="plus" go="lobby-create">
        Criar lobby manual
      </Btn>
    </Page>
  );
}

function LobbyCreate() {
  const [visibility, setVisibility] = useState('Aberto');
  return (
    <Page title="Criar lobby">
      <Field label="Formato">
        <Seg>
          <SegBtn on>Futebol 5x5</SegBtn>
          <SegBtn>Vôlei 6x6</SegBtn>
        </Seg>
      </Field>
      <View style={{ flexDirection: 'row', gap: 10 }}>
        <View style={{ flex: 1 }}>
          <Field label="Data">
            <Input defaultValue="2026-11-17" maxLength={10} />
          </Field>
        </View>
        <View style={{ flex: 1 }}>
          <Field label="Horário">
            <Input defaultValue="20:00" maxLength={5} />
          </Field>
        </View>
      </View>
      <Field label="Local">
        <Input defaultValue="Arena Sul · Centro" placeholder="Buscar quadra" maxLength={120} />
      </Field>
      <Field label="Visibilidade">
        <Seg>
          {['Aberto', 'Fechado'].map((item) => (
            <SegBtn key={item} on={visibility === item} onPress={() => setVisibility(item)}>
              {item}
            </SegBtn>
          ))}
        </Seg>
      </Field>
      <Notice tone="blue" icon="lock">
        Lobby fechado é benefício do passe.
      </Notice>
      <Btn tone="primary" go="lobby-detail">
        Criar lobby
      </Btn>
    </Page>
  );
}

function LobbyVote() {
  const nav = useNav();
  const [vote, setVote] = useState<'yes' | 'no' | null>(null);
  return (
    <Page title="Troca de quadra">
      <Card>
        <Row between>
          <Badge tone="lime">PROPOSTA</Badge>
          <Txt variant="tiny">expira em 18 min</Txt>
        </Row>
        <Txt variant="h2" style={{ marginTop: 8, marginBottom: 2 }}>
          Arena Norte
        </Txt>
        <Txt variant="tiny">Ter, 17 nov · 20:00 · 8,1 km · mesma faixa</Txt>
      </Card>
      <Card>
        <Row between>
          <Txt variant="h3">Votos</Txt>
          <Badge>6 de 10</Badge>
        </Row>
        <View style={{ marginTop: 10, marginBottom: 10 }}>
          <Progress value={60} />
        </View>
        <Row between>
          <Txt variant="tiny">6 sim · 2 não · 2 sem voto</Txt>
          <Txt variant="tiny">quórum 50%</Txt>
        </Row>
      </Card>
      <Notice tone="orange" icon="alert">
        Aprovação exige maioria. A reserva atual não é cancelada automaticamente.
      </Notice>
      <BtnRow>
        <Btn
          tone={vote === 'yes' ? 'primary' : 'ghost'}
          onPress={() => {
            setVote('yes');
            nav.toast('Voto sim registrado no protótipo');
          }}
        >
          Votar sim
        </Btn>
        <Btn
          tone={vote === 'no' ? 'primary' : 'ghost'}
          onPress={() => {
            setVote('no');
            nav.toast('Voto não registrado no protótipo');
          }}
        >
          Votar não
        </Btn>
      </BtnRow>
      {vote ? (
        <Notice tone="lime" icon="check">
          Seu voto foi registrado. O resultado aparece para todos quando a votação encerrar.
        </Notice>
      ) : null}
    </Page>
  );
}

function LobbyCanceled() {
  return (
    <Page title="Partida">
      <StateScreen
        icon="alert"
        title="Lobby desfeito"
        text="Não houve confirmação suficiente. Já estamos buscando outra partida para você."
        actions={
          <>
            <Btn tone="primary" go="home">
              Cancelar fila
            </Btn>
            <Btn tone="ghost" go="notifications">
              Ver notificações
            </Btn>
          </>
        }
      />
    </Page>
  );
}

function LobbyFull() {
  return (
    <Page title="Partida cheia">
      <StateScreen
        icon="users"
        title="Todas as vagas ocupadas"
        text="A partida está cheia. Você pode entrar na fila de espera; se alguém sair, o convite respeita a ordem e o prazo."
        actions={
          <>
            <Btn tone="primary" toast="Você entrou na espera no protótipo">
              Entrar na espera
            </Btn>
            <Btn tone="ghost" go="queue-casual">
              Ver outras partidas
            </Btn>
          </>
        }
      />
    </Page>
  );
}

function ProfileMe() {
  const nav = useNav();
  const { palette } = useTheme();
  const {
    profile,
    progress,
    ratings,
    stats,
    clan,
    primaryFormatId,
    loadRating,
    onboarding,
    loadStats,
    loadSeason,
    badges,
  } = useApp();
  const { width } = useWindowDimensions();
  const avatarSize = width < 360 ? 88 : 112;
  const formatId = primaryFormatId;
  useEffect(() => {
    if (formatId) {
      loadRating(formatId).catch(() => undefined);
    }
  }, [formatId, loadRating]);
  useEffect(() => {
    loadStats().catch(() => undefined);
  }, [loadStats]);
  useEffect(() => {
    loadSeason().catch(() => undefined);
  }, [loadSeason]);
  const rating = formatId ? ratings[formatId] : undefined;
  const name = profile?.display_name ?? onboarding.displayName ?? 'Jogador';
  const personalClan = clan?.name ?? 'Sem clã';
  const level = progress?.level ?? 0;
  const tier = progress?.tier ?? 'Bronze';
  const xp = progress?.xp_total ?? 0;
  const matches = stats?.totals.matches ?? 0;
  const wins = stats?.totals.wins ?? 0;
  const presence =
    stats?.totals.presence_rate != null ? `${Math.round(stats.totals.presence_rate * 100)}%` : '—';
  const sports = profile?.sports ?? [];
  const availability = profile?.availability.length
    ? profile.availability
        .map(
          (window) =>
            `${WEEKDAY_NAMES[window.weekday - 1]} · ${window.start_time.slice(0, 5)}–${window.end_time.slice(0, 5)}`,
        )
        .join(' · ')
    : 'Nenhum horário cadastrado';
  const division = rating?.provisional
    ? 'Provisório'
    : rating
      ? divisionLabel(rating.division)
      : '—';
  const tag = profile?.user_id ? profile.user_id.slice(0, 4).toUpperCase() : '----';
  const now = new Date();
  const seasonLabel = `T${Math.floor(now.getMonth() / 3) + 1} ${now.getFullYear()}`;
  return (
    <Page title="Perfil">
      <Card padding={18}>
        <Row style={{ gap: 14 }}>
          <View
            style={{
              padding: 3,
              borderWidth: 2,
              borderColor: palette.lineStrong,
              borderRadius: avatarSize / 2 + 4,
            }}
          >
            <Avatar size={avatarSize} {...onboarding.avatar} palette={palette} />
          </View>
          <View style={{ flex: 1 }}>
            <Txt variant="h1" style={{ fontSize: 26 }}>
              {name}
            </Txt>
            <Txt variant="tiny">
              #{tag} · {personalClan}
            </Txt>
            <View style={{ flexDirection: 'row', gap: 6, marginTop: 7, flexWrap: 'wrap' }}>
              <Badge>{`${tier.toUpperCase()} ${level}`}</Badge>
              <Badge tone="blue">{division}</Badge>
            </View>
          </View>
        </Row>
        <Row
          between
          style={{
            marginTop: 14,
            paddingTop: 12,
            borderTopWidth: 1.5,
            borderTopColor: palette.line,
          }}
        >
          <View>
            <Txt variant="label">Divisão</Txt>
            <Txt variant="h3">{division}</Txt>
            <Txt variant="tiny">{seasonLabel} · reseta na virada</Txt>
          </View>
          <View style={{ alignItems: 'flex-end' }}>
            <Txt variant="label">Nível</Txt>
            <Txt variant="h3">{`${tier} ${level}`}</Txt>
            <Txt variant="tiny">temporada · {number(xp)} XP</Txt>
          </View>
        </Row>
        <View style={{ marginTop: 10 }}>
          <Progress value={Math.min(100, Math.round((rating?.progress ?? 0) * 100))} />
        </View>
      </Card>
      <View style={{ flexDirection: 'row', gap: 8 }}>
        <Card style={{ flex: 1 }} padding={12}>
          <Txt variant="num" align="center" style={{ fontSize: 24 }}>
            {matches}
          </Txt>
          <Txt variant="tiny" align="center">
            partidas
          </Txt>
        </Card>
        <Card style={{ flex: 1 }} padding={12}>
          <Txt variant="num" align="center" style={{ fontSize: 24 }}>
            {wins}
          </Txt>
          <Txt variant="tiny" align="center">
            vitórias
          </Txt>
        </Card>
        <Card style={{ flex: 1 }} padding={12}>
          <Txt variant="num" align="center" style={{ fontSize: 24 }}>
            {presence}
          </Txt>
          <Txt variant="tiny" align="center">
            presença
          </Txt>
        </Card>
      </View>
      <CardList>
        {[
          {
            icon: 'trophy' as const,
            title: 'Minha evolução',
            sub: 'Divisão por formato',
            go: 'stats-evolution',
          },
          {
            icon: 'pin' as const,
            title: 'Minhas quadras',
            sub: 'Histórico por quadra',
            go: 'stats-venues',
          },
          {
            icon: 'globe' as const,
            title: 'Meu passaporte',
            sub: 'Quadras visitadas',
            go: 'stats-passport',
          },
          {
            icon: 'clock' as const,
            title: 'Meus horários',
            sub: 'Dias e formatos',
            go: 'stats-times',
          },
          {
            icon: 'globe' as const,
            title: 'Rede',
            sub: 'Onde e quando tem mais jogo',
            go: 'stats',
          },
        ].map((item, index, all) => (
          <ListRow key={item.title} last={index === all.length - 1} onPress={() => nav.go(item.go)}>
            <IconBtn icon={item.icon} label={item.title} plain go={item.go} />
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                {item.title}
              </Text>
              <Text style={{ fontSize: 13, color: palette.muted }}>{item.sub}</Text>
            </View>
            <Text style={{ color: palette.muted }}>›</Text>
          </ListRow>
        ))}
      </CardList>
      <CardList>
        {[
          {
            icon: 'wallet' as const,
            title: 'Ingressos',
            sub: 'Ingressos, passe e extrato',
            go: 'wallet',
          },
          {
            icon: 'cal' as const,
            title: 'Histórico de reservas',
            sub: 'Reservas, status e comprovantes',
            go: 'booking-history',
          },
          {
            icon: 'clan' as const,
            title: 'Meu clã',
            sub: 'Membros, chat e troféus',
            go: 'clan',
          },
          {
            icon: 'trophy' as const,
            title: 'Ranking',
            sub: 'Sua posição por modalidade',
            go: 'ranking',
          },
          {
            icon: 'gear' as const,
            title: 'Configurações',
            sub: 'Conta, segurança, privacidade e LGPD',
            go: 'settings',
          },
        ].map((item, index, all) => (
          <ListRow key={item.title} last={index === all.length - 1} onPress={() => nav.go(item.go)}>
            <IconBtn icon={item.icon} label={item.title} plain go={item.go} />
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                {item.title}
              </Text>
              <Text style={{ fontSize: 13, color: palette.muted }}>{item.sub}</Text>
            </View>
            <Text style={{ color: palette.muted }}>›</Text>
          </ListRow>
        ))}
      </CardList>
      <Card>
        <Row between>
          <Txt variant="h3">Insígnias</Txt>
          <Txt variant="tiny">{Math.min(badges.length, 3)}/3 em destaque</Txt>
        </Row>
        <View style={{ flexDirection: 'row', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
          {badges.length ? (
            badges.slice(0, 3).map((badge) => (
              <Badge key={badge.badge_id} tone={badge.kind === 'founder' ? 'default' : 'lime'}>
                {badge.name.toUpperCase()}
              </Badge>
            ))
          ) : (
            <Txt variant="tiny">Nenhuma insígnia ainda.</Txt>
          )}
        </View>
        <Row between style={{ marginTop: 12 }}>
          <Txt variant="h3">Medalhas</Txt>
          <TextBtn go="badges">Ver todas</TextBtn>
        </Row>
        <Txt variant="tiny" style={{ marginTop: 4 }}>
          {badges.some((badge) => badge.kind === 'medal')
            ? 'Medalha é conquista competitiva; insígnia marca temporada ou fundador.'
            : 'Nenhuma medalha ainda.'}
        </Txt>
      </Card>
      <Card>
        <Row between>
          <Txt variant="h3">Modalidades</Txt>
          <TextBtn go="sports">Editar</TextBtn>
        </Row>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
          {sports.length ? (
            <>
              {sports.map((sport) => (
                <Badge key={sport.format_id}>{sport.format_name.toUpperCase()}</Badge>
              ))}
              <Badge>{levelLabel(sports[0].level).toUpperCase()}</Badge>
            </>
          ) : (
            <Txt variant="tiny">Nenhuma modalidade cadastrada.</Txt>
          )}
        </View>
        <Divider style={{ marginVertical: 12 }} />
        <Row between>
          <Txt variant="h3">Disponibilidade</Txt>
          <TextBtn go="availability">Editar</TextBtn>
        </Row>
        <Txt variant="tiny" style={{ marginTop: 5 }}>
          {availability}
        </Txt>
      </Card>
      <BtnRow>
        <Btn tone="primary" go="profile-edit">
          Editar perfil
        </Btn>
        <Btn tone="ghost" modal="share">
          Compartilhar
        </Btn>
      </BtnRow>
    </Page>
  );
}

function ProfileOther() {
  const nav = useNav();
  const { palette } = useTheme();
  const { matches } = useApp();
  const name = typeof nav.params.name === 'string' ? nav.params.name : 'Jogador';
  const userId = typeof nav.params.userId === 'string' ? nav.params.userId : '';
  const tag = userId ? userId.slice(0, 4).toUpperCase() : '----';
  return (
    <Page title="Perfil do jogador">
      <Card>
        <Row style={{ gap: 14 }}>
          <Avatar
            size={112}
            skin="#62686E"
            hair="#17191B"
            shirt="#62686E"
            style={2}
            glasses
            palette={palette}
          />
          <View style={{ flex: 1 }}>
            <Txt variant="h1" style={{ fontSize: 26 }}>
              {name}
            </Txt>
            <Txt variant="tiny">#{tag}</Txt>
            <View style={{ flexDirection: 'row', gap: 6, marginTop: 7 }}>
              <Badge>PERFIL PÚBLICO</Badge>
            </View>
          </View>
        </Row>
        <Row
          between
          style={{
            marginTop: 14,
            paddingTop: 12,
            borderTopWidth: 1.5,
            borderTopColor: palette.line,
          }}
        >
          <View>
            <Txt variant="label">Divisão</Txt>
            <Txt variant="h3">—</Txt>
          </View>
          <View style={{ alignItems: 'flex-end' }}>
            <Txt variant="label">Nível</Txt>
            <Txt variant="h3">—</Txt>
          </View>
        </Row>
      </Card>
      <View style={{ flexDirection: 'row', gap: 8 }}>
        <Card style={{ flex: 1 }} padding={12}>
          <Txt variant="num" align="center" style={{ fontSize: 24 }}>
            —
          </Txt>
          <Txt variant="tiny" align="center">
            partidas
          </Txt>
        </Card>
        <Card style={{ flex: 1 }} padding={12}>
          <Txt variant="num" align="center" style={{ fontSize: 24 }}>
            —
          </Txt>
          <Txt variant="tiny" align="center">
            vitórias
          </Txt>
        </Card>
        <Card style={{ flex: 1 }} padding={12}>
          <Txt variant="num" align="center" style={{ fontSize: 24 }}>
            —
          </Txt>
          <Txt variant="tiny" align="center">
            streak
          </Txt>
        </Card>
      </View>
      <Card>
        <Row between>
          <Txt variant="h3">Conquistas</Txt>
          <Txt variant="tiny">públicas</Txt>
        </Row>
        <Txt variant="tiny" style={{ marginTop: 8 }}>
          Sem conquistas públicas.
        </Txt>
      </Card>
      <BtnRow>
        <Btn tone="primary" go="lobby-invite">
          Convidar
        </Btn>
        <Btn tone="ghost" go="add-friend">
          Adicionar amigo
        </Btn>
      </BtnRow>
      <BtnRow>
        <Btn tone="ghost" modal="block">
          Bloquear
        </Btn>
        <Btn
          tone="ghost"
          onPress={() =>
            nav.go('report-profile', {
              userId,
              name,
              lobbyId: matches.find((match) => match.lobby_id)?.lobby_id,
            })
          }
        >
          Denunciar
        </Btn>
      </BtnRow>
      <Notice tone="blue" icon="shield">
        Telefone, e-mail e localização exata não aparecem para outros jogadores.
      </Notice>
    </Page>
  );
}

function ProfileEdit() {
  const nav = useNav();
  const { palette } = useTheme();
  const { profile, onboarding, session, loadProfile, email } = useApp();
  const [name, setName] = useState(profile?.display_name ?? '');
  const [bio, setBio] = useState(profile?.bio ?? '');
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true);
    try {
      if (session) {
        await api.profile.update(session.accessToken, name, bio);
        await loadProfile();
      }
      nav.back();
    } catch (error) {
      toastError(nav, error);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Page title="Editar perfil">
      <Row style={{ gap: 14 }}>
        <Avatar size={86} {...onboarding.avatar} palette={palette} />
        <View style={{ flex: 1 }}>
          <Txt variant="h3">Avatar</Txt>
          <Txt variant="tiny">Catálogo fechado · sem upload</Txt>
          <View style={{ marginTop: 6 }}>
            <Btn tone="ghost" small block={false} go="avatar-editor">
              Editar camadas
            </Btn>
          </View>
        </View>
      </Row>
      <Field label="Nome de exibição">
        <Input value={name} onChangeText={setName} maxLength={60} placeholder="Seu nome" />
      </Field>
      <Field label="Tag">
        <Input
          defaultValue={profile?.user_id ? `#${profile.user_id.slice(0, 4).toUpperCase()}` : ''}
          editable={false}
        />
      </Field>
      <Field label="Bio">
        <Input
          value={bio}
          onChangeText={setBio}
          multiline
          maxLength={280}
          placeholder="Conte um pouco sobre você"
          style={{ minHeight: 110, textAlignVertical: 'top' }}
        />
      </Field>
      <CardList>
        {[
          {
            icon: 'bolt' as const,
            title: 'Modalidades e formatos',
            sub: 'Futebol 5x5 · Vôlei 6x6',
            go: 'sports',
          },
          {
            icon: 'cal' as const,
            title: 'Disponibilidade semanal',
            sub: '3 janelas',
            go: 'availability',
          },
          {
            icon: 'pin' as const,
            title: 'Região',
            sub: profile?.region
              ? `${profile.region.city ?? 'Região'} · ${profile.region.radius_km} km`
              : 'Definir região',
            go: 'region',
          },
          {
            icon: 'wallet' as const,
            title: 'E-mail para pagamento',
            sub: email ?? 'Não informado',
            go: 'payment-email',
          },
          {
            icon: 'shield' as const,
            title: 'CPF para nota fiscal',
            sub: 'Usado na NFS-e do espaço e da intermediação',
            go: 'cpf',
          },
        ].map((item, index, all) => (
          <ListRow key={item.title} last={index === all.length - 1} onPress={() => nav.go(item.go)}>
            <IconBtn icon={item.icon} label={item.title} plain go={item.go} />
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                {item.title}
              </Text>
              <Text style={{ fontSize: 13, color: palette.muted }}>{item.sub}</Text>
            </View>
            <Text style={{ color: palette.muted }}>›</Text>
          </ListRow>
        ))}
      </CardList>
      <Btn tone="primary" onPress={save} disabled={busy}>
        Salvar alterações
      </Btn>
    </Page>
  );
}

function AvatarEditor() {
  const nav = useNav();
  const { palette } = useTheme();
  const { onboarding, setOnboarding } = useApp();
  const [tab, setTab] = useState<'skin' | 'hair' | 'shirt' | 'accessory'>('skin');
  const [avatar, setAvatar] = useState(onboarding.avatar);
  const [hairStyle, setHairStyle] = useState('Médio');
  const [shirtStyle, setShirtStyle] = useState('Camisa');
  const [accessory, setAccessory] = useState('Sem acessório');
  const skins = ['#F1F3F0', '#D5D9D6', '#A6ABB1', '#A6ABB1', '#62686E'];
  const hairs = ['#17191B', '#383D43', '#62686E', '#A6ABB1', '#D5D9D6'];
  const shirts = ['#62686E', '#62686E', '#E53935', '#62686E', '#17191B'];
  const save = () => {
    setOnboarding({ avatar: { ...avatar, glasses: accessory === 'Óculos' } });
    nav.back();
  };
  return (
    <Page title="Editar avatar">
      <View style={{ alignItems: 'center', paddingVertical: 8 }}>
        <Avatar size={112} {...avatar} palette={palette} />
      </View>
      <Seg>
        {[
          ['skin', 'Pele'],
          ['hair', 'Cabelo'],
          ['shirt', 'Roupa'],
          ['accessory', 'Acessório'],
        ].map(([key, label]) => (
          <SegBtn key={key} on={tab === key} onPress={() => setTab(key as typeof tab)}>
            {label}
          </SegBtn>
        ))}
      </Seg>
      {tab === 'skin' ? (
        <Card>
          <Txt variant="h3">Tom de pele</Txt>
          <View style={{ flexDirection: 'row', gap: 10, marginTop: 10 }}>
            {skins.map((color, index) => (
              <View
                key={`${color}-${index}`}
                onTouchEnd={() => setAvatar((current) => ({ ...current, skin: color }))}
                style={{
                  width: 46,
                  height: 46,
                  borderRadius: 23,
                  backgroundColor: color,
                  borderWidth: avatar.skin === color && index === 2 ? 2 : 1.5,
                  borderColor: avatar.skin === color && index === 2 ? '#17191B' : palette.line,
                }}
              />
            ))}
          </View>
        </Card>
      ) : null}
      {tab === 'hair' ? (
        <Card>
          <Txt variant="h3">Cabelo</Txt>
          <ChipRow style={{ marginTop: 10 }}>
            {['Curto', 'Médio', 'Cacheado', 'Raspado'].map((item) => (
              <Chip key={item} on={hairStyle === item} onPress={() => setHairStyle(item)}>
                {item}
              </Chip>
            ))}
          </ChipRow>
          <Txt variant="h3" style={{ marginTop: 16 }}>
            Cor
          </Txt>
          <View style={{ flexDirection: 'row', gap: 10, marginTop: 10 }}>
            {hairs.map((color, index) => (
              <View
                key={`${color}-${index}`}
                onTouchEnd={() => setAvatar((current) => ({ ...current, hair: color }))}
                style={{
                  width: 46,
                  height: 46,
                  borderRadius: 23,
                  backgroundColor: color,
                  borderWidth: avatar.hair === color && index === 0 ? 2 : 1.5,
                  borderColor: avatar.hair === color && index === 0 ? '#17191B' : palette.line,
                }}
              />
            ))}
          </View>
        </Card>
      ) : null}
      {tab === 'shirt' ? (
        <Card>
          <Txt variant="h3">Roupa</Txt>
          <ChipRow style={{ marginTop: 10 }}>
            {['Camisa', 'Regata', 'Moletom'].map((item) => (
              <Chip key={item} on={shirtStyle === item} onPress={() => setShirtStyle(item)}>
                {item}
              </Chip>
            ))}
          </ChipRow>
          <Txt variant="h3" style={{ marginTop: 16 }}>
            Cor
          </Txt>
          <View style={{ flexDirection: 'row', gap: 10, marginTop: 10 }}>
            {shirts.map((color, index) => (
              <View
                key={`${color}-${index}`}
                onTouchEnd={() => setAvatar((current) => ({ ...current, shirt: color }))}
                style={{
                  width: 46,
                  height: 46,
                  borderRadius: 23,
                  backgroundColor: color,
                  borderWidth: avatar.shirt === color && index === 0 ? 2 : 1.5,
                  borderColor: avatar.shirt === color && index === 0 ? '#17191B' : palette.line,
                }}
              />
            ))}
          </View>
        </Card>
      ) : null}
      {tab === 'accessory' ? (
        <Card>
          <Txt variant="h3">Acessório</Txt>
          <ChipRow style={{ marginTop: 10 }}>
            {['Sem acessório', 'Óculos', 'Boné', 'Brinco'].map((item) => (
              <Chip key={item} on={accessory === item} onPress={() => setAccessory(item)}>
                {item}
              </Chip>
            ))}
          </ChipRow>
        </Card>
      ) : null}
      <Btn tone="primary" onPress={save}>
        Salvar avatar
      </Btn>
    </Page>
  );
}

function Sports() {
  const { profile, onboarding } = useApp();
  const sports = profile?.sports.length
    ? profile.sports
    : [
        {
          format_id: 'f5',
          sport_slug: 'futebol',
          sport_name: 'Futebol',
          format_name: 'Futebol 5x5',
          level: onboarding.level,
          court_preference: onboarding.courtPreference,
        },
        {
          format_id: 'v6',
          sport_slug: 'volei',
          sport_name: 'Vôlei',
          format_name: 'Vôlei 6x6',
          level: 'beginner',
          court_preference: 'PRIVATE_ONLY',
        },
      ];
  return (
    <Page title="Modalidades e formatos">
      {sports.map((sport) => (
        <Card key={sport.format_id}>
          <Row between>
            <Txt variant="h3">{sport.format_name}</Txt>
            <Badge tone="green">ATIVO</Badge>
          </Row>
          <Txt variant="tiny" style={{ marginTop: 4, marginBottom: 10 }}>
            {sport.format_id === 'v6'
              ? 'Formato em validação · duração definida pelo formato'
              : '10 jogadores · duração definida pelo formato'}
          </Txt>
          <Kv label="Nível autodeclarado" value={levelLabel(sport.level)} />
          <Kv label="Preferência de quadra" value={courtLabel(sport.court_preference)} />
          {sport.format_name.toLowerCase().includes('futebol') ? (
            <Kv label="Posição" value="Ala" />
          ) : null}
        </Card>
      ))}
      <Notice tone="orange" icon="info">
        Nível autodeclarado não é divisão. A divisão só aparece em partidas ranqueadas.
      </Notice>
      <Btn tone="ghost" icon="plus" toast="Modalidade adicionada no protótipo">
        Adicionar modalidade
      </Btn>
      <Btn tone="primary" back>
        Salvar
      </Btn>
    </Page>
  );
}

const WEEKDAYS = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];

function Availability() {
  const nav = useNav();
  const { palette } = useTheme();
  const { profile, session, loadProfile } = useApp();
  const [windows, setWindows] = useState(profile?.availability.length ? profile.availability : []);
  const [editorDay, setEditorDay] = useState<number | null>(null);
  const save = async () => {
    try {
      if (session) {
        await api.profile.replaceAvailability(session.accessToken, windows);
        await loadProfile();
      }
      nav.back();
    } catch (error) {
      toastError(nav, error);
    }
  };
  return (
    <>
      <Page title="Disponibilidade">
        <Card tone="flat">
          <Row between>
            <Txt variant="h3">Fuso</Txt>
            <Pill icon="globe">America/Sao_Paulo</Pill>
          </Row>
        </Card>
        <CardList>
          {WEEKDAYS.map((day, index) => {
            const weekday = index + 1;
            const list = windows.filter((window) => window.weekday === weekday);
            return (
              <ListRow key={day} last={index === WEEKDAYS.length - 1}>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>{day}</Text>
                  <Text style={{ fontSize: 13, color: palette.muted, marginTop: 2 }}>
                    {list.length
                      ? list
                          .map(
                            (window) =>
                              `${window.start_time.slice(0, 5)}-${window.end_time.slice(0, 5)}`,
                          )
                          .join('\n')
                      : '-'}
                  </Text>
                </View>
                <IconBtn
                  icon="plus"
                  label={`Adicionar horário de ${day}`}
                  onPress={() => setEditorDay(weekday)}
                />
              </ListRow>
            );
          })}
        </CardList>
        <Btn tone="primary" onPress={save}>
          Salvar disponibilidade
        </Btn>
      </Page>
      <AddWindowSheet
        key={editorDay ?? 'closed'}
        visible={editorDay !== null}
        initialWeekday={editorDay ?? 1}
        onClose={() => setEditorDay(null)}
        onAdd={(window) => setWindows((current) => [...current, window])}
      />
    </>
  );
}

function Region() {
  const nav = useNav();
  const { palette } = useTheme();
  const { profile, session, setProfile, loadProfile } = useApp();
  const [radius, setRadius] = useState(profile?.region?.radius_km ?? 8);
  const [busy, setBusy] = useState(false);
  const locate = async () => {
    setBusy(true);
    try {
      const permission = await Location.requestForegroundPermissionsAsync();
      if (permission.status !== 'granted') {
        nav.toast('Localização não autorizada.');
        return;
      }
      const position = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });
      if (session) {
        const updated = await api.profile.setRegionLocation(
          session.accessToken,
          position.coords.latitude,
          position.coords.longitude,
          radius,
        );
        setProfile(updated);
      }
      nav.toast('GPS aproximado ativado no protótipo');
    } catch {
      nav.toast('Não foi possível obter a localização.');
    } finally {
      setBusy(false);
    }
  };
  const save = async () => {
    await locate();
    if (session) {
      await loadProfile().catch(() => undefined);
    }
    nav.back();
  };
  return (
    <Page title="Região">
      <Card>
        <Row between>
          <Txt variant="h3">Localização do aparelho</Txt>
          <Badge tone="green">GRÁTIS</Badge>
        </Row>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 10 }}>
          <IconBtn icon="pin" label="Usar GPS" ink onPress={locate} />
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
              {profile?.region?.city ??
                (profile?.region ? 'Região aproximada' : 'Sem região definida')}
            </Text>
            <Text style={{ fontSize: 13, color: palette.muted }}>
              {profile?.region
                ? `precisão aproximada · raio de ${radius} km`
                : 'Use o GPS para definir sua região'}
            </Text>
          </View>
          <Badge tone={profile?.region ? 'lime' : 'default'}>
            {profile?.region ? 'ATIVO' : 'DEFINIR'}
          </Badge>
        </View>
      </Card>
      <Card>
        <Row between>
          <Txt variant="h3">Busca por CEP</Txt>
          <Badge tone="blue">PASSE</Badge>
        </Row>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 10 }}>
          <IconBtn icon="search" label="Buscar CEP" go="region-cep-locked" />
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
              Declarar intenção em outro lugar
            </Text>
            <Text style={{ fontSize: 13, color: palette.muted }}>Disponível no passe</Text>
          </View>
          <Text style={{ color: palette.muted }}>▣</Text>
        </View>
      </Card>
      <Card>
        <Row between>
          <Txt variant="h3">Raio de busca</Txt>
          <Badge>{radius} km</Badge>
        </Row>
        <View style={{ marginTop: 8 }}>
          <Range min={1} max={50} value={radius} onChange={setRadius} />
        </View>
        <Row between>
          <Txt variant="tiny">1 km</Txt>
          <Txt variant="tiny">50 km</Txt>
        </Row>
      </Card>
      <Photo tone="blue">
        <PhotoCap badge={<Badge>LGPD</Badge>}>
          Quadras com endereço exato · sua localização permanece aproximada
        </PhotoCap>
      </Photo>
      <Btn tone="primary" onPress={save} disabled={busy}>
        Salvar região
      </Btn>
    </Page>
  );
}

function RegionCepLocked() {
  return (
    <Page title="Busca por CEP">
      <StateScreen
        icon="lock"
        title="CEP é do passe"
        text="O plano gratuito busca pela localização do aparelho. O CEP permite declarar intenção em qualquer lugar e sobrecarrega o motor com partidas que não vão acontecer."
        actions={
          <>
            <Btn tone="primary" go="pass">
              Conhecer o passe
            </Btn>
            <Btn tone="ghost" go="region">
              Usar localização
            </Btn>
          </>
        }
      />
    </Page>
  );
}

export const coreScreens: ScreenDef[] = [
  { id: 'home', tab: 'jogar', render: () => <Home /> },
  { id: 'queue-casual', tab: 'jogar', render: () => <QueueScreen mode="casual" /> },
  { id: 'queue-ranked', tab: 'jogar', render: () => <QueueScreen mode="ranked" /> },
  { id: 'queue-search', tab: 'jogar', render: () => <QueueSearch /> },
  { id: 'queue-empty', tab: 'jogar', render: () => <QueueEmpty /> },
  { id: 'queue-restricted', tab: 'jogar', render: () => <QueueRestricted /> },
  { id: 'lobby-found', tab: 'jogar', render: () => <LobbyFound /> },
  { id: 'lobby-detail', tab: 'jogar', render: () => <LobbyDetail /> },
  { id: 'lobby-t1', tab: 'jogar', render: () => <LobbyT1 /> },
  { id: 'lobby-chat', tab: 'jogar', render: () => <LobbyChat /> },
  { id: 'lobby-invite', tab: 'jogar', render: () => <LobbyInvite /> },
  { id: 'lobby-invite-received', tab: 'social', render: () => <LobbyInviteReceived /> },
  { id: 'lobby-open', tab: 'jogar', hidden: true, render: () => <LobbyOpen /> },
  { id: 'lobby-create', tab: 'jogar', hidden: true, render: () => <LobbyCreate /> },
  { id: 'lobby-vote', tab: 'jogar', hidden: true, render: () => <LobbyVote /> },
  { id: 'lobby-canceled', tab: 'jogar', render: () => <LobbyCanceled /> },
  { id: 'lobby-full', tab: 'jogar', hidden: true, render: () => <LobbyFull /> },
  { id: 'profile-me', tab: 'perfil', render: () => <ProfileMe /> },
  { id: 'profile-other', tab: 'social', render: () => <ProfileOther /> },
  { id: 'profile-edit', tab: 'perfil', render: () => <ProfileEdit /> },
  { id: 'avatar-editor', tab: 'perfil', render: () => <AvatarEditor /> },
  { id: 'sports', tab: 'perfil', render: () => <Sports /> },
  { id: 'availability', tab: 'perfil', render: () => <Availability /> },
  { id: 'region', tab: 'perfil', render: () => <Region /> },
  { id: 'region-cep-locked', tab: 'perfil', render: () => <RegionCepLocked /> },
];
