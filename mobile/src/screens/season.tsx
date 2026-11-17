import { useEffect, useMemo, useState } from 'react';
import { Pressable, View } from 'react-native';

import { api } from '../api/client';
import type { TrackLevel } from '../api/types';
import { useApp } from '../state/app';
import { useNav, useTheme } from '../state/context';
import {
  Badge,
  Btn,
  BtnRow,
  Card,
  CardList,
  Chip,
  ChipRow,
  Kv,
  ListRow,
  LoadingState,
  Notice,
  Page,
  Progress,
  Row,
  StateScreen,
  Txt,
} from '../ui/kit';
import { number } from '../ui/datetime';
import { Text } from '../ui/text';
import type { ScreenDef } from './types';

const MILESTONES = [4, 8, 12, 17, 21, 26, 30];
const ITEM_DEFS: [number, string, string][] = [
  [4, 'Acessório de personagem', 'free'],
  [8, 'Animação de lobby', 'pass'],
  [12, 'Emote de chat', 'free'],
  [17, 'Ícone de entrada', 'pass'],
  [21, 'Acessório raro', 'free'],
  [26, 'Efeito de perfil', 'pass'],
  [30, 'Insígnia da temporada', 'free'],
];

function useSeasonData() {
  const { progress, track, missions, loadSeason } = useApp();
  const [now] = useState(() => Date.now());
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    loadSeason()
      .catch(() => {
        if (active) {
          setFailed(true);
        }
      })
      .finally(() => {
        if (active) {
          setLoaded(true);
        }
      });
    return () => {
      active = false;
    };
  }, [loadSeason]);
  const retry = () => {
    setLoaded(false);
    setFailed(false);
    loadSeason()
      .catch(() => setFailed(true))
      .finally(() => setLoaded(true));
  };
  const xp = progress?.xp_total ?? 3450;
  const level = progress?.level ?? 23;
  const tier = progress?.tier ?? 'Ouro';
  const maxXp = track?.levels[track.levels.length - 1]?.xp_required ?? 4500;
  const percent = Math.min(100, Math.round((xp / Math.max(1, maxXp)) * 100));
  const days = progress
    ? Math.max(0, Math.ceil((new Date(progress.season.ends_at).getTime() - now) / 86_400_000))
    : 0;
  const completedMissions = missions.length ? missions.filter((item) => item.completed).length : 0;
  return {
    progress,
    track,
    missions,
    xp,
    level,
    tier,
    maxXp,
    percent,
    days,
    completedMissions,
    loaded,
    failed,
    retry,
  };
}

function Season() {
  const nav = useNav();
  const {
    progress,
    xp,
    level,
    tier,
    maxXp,
    percent,
    days,
    completedMissions,
    loaded,
    failed,
    retry,
  } = useSeasonData();
  const { palette } = useTheme();
  const seasonCode = progress?.season.code ?? '2026-Q4';
  if (!loaded) {
    return (
      <Page title={`Temporada ${seasonCode}`}>
        <LoadingState label="Buscando sua temporada." variant="season" />
      </Page>
    );
  }
  if (failed) {
    return (
      <Page title={`Temporada ${seasonCode}`}>
        <StateScreen
          icon="wifi-off"
          title="Não foi possível carregar a temporada"
          text="Verifique a conexão e tente novamente. Seu progresso não foi alterado."
          actions={
            <Btn tone="primary" onPress={retry}>
              Tentar novamente
            </Btn>
          }
        />
      </Page>
    );
  }
  return (
    <Page title={`Temporada ${seasonCode}`}>
      <Card tone="ink">
        <Row between>
          <Badge tone="lime">{`${tier.toUpperCase()} ${level}`}</Badge>
          <Badge>{days} DIAS</Badge>
        </Row>
        <Txt
          variant="display"
          color="onInk"
          style={{ fontSize: 32, marginTop: 12, marginBottom: 4 }}
        >
          {number(xp)} XP
        </Txt>
        <Txt variant="tiny" color="softOnInk">
          faltam {number(Math.max(0, maxXp - xp))} XP para o nível 30
        </Txt>
        <View style={{ marginTop: 12 }}>
          <Progress value={percent} tone="orange" />
        </View>
        <Row between style={{ marginTop: 7 }}>
          <Txt variant="tiny" color="softOnInk">
            Nível {level}
          </Txt>
          <Txt variant="tiny" color="softOnInk">
            Nível 30 · insígnia
          </Txt>
        </Row>
      </Card>
      <View style={{ flexDirection: 'row', gap: 8 }}>
        <Card style={{ flex: 1 }} onPress={() => nav.go('missions')}>
          <Txt variant="label">Missões</Txt>
          <Txt variant="num" style={{ fontSize: 28 }}>
            {completedMissions}/{Math.max(3, 3)}
          </Txt>
          <Txt variant="tiny">da semana</Txt>
        </Card>
        <Card style={{ flex: 1 }} onPress={() => nav.go('streak')}>
          <Txt variant="label">Streak</Txt>
          <Txt variant="num" style={{ fontSize: 28 }}>
            {progress?.streak.current ?? 0}
          </Txt>
          <Txt variant="tiny">vitórias</Txt>
        </Card>
      </View>
      <Card onPress={() => nav.go('season-track')}>
        <Row between>
          <Txt variant="h3">Trilha</Txt>
          <Badge>30 níveis</Badge>
        </Row>
        <View style={{ flexDirection: 'row', gap: 7, marginTop: 10 }}>
          {MILESTONES.map((item, index) => (
            <View
              key={item}
              style={{
                flex: 1,
                minHeight: 54,
                borderRadius: 10,
                borderWidth: 1.5,
                borderColor: palette.line,
                backgroundColor: item < level ? palette.surface2 : palette.surface,
                alignItems: 'center',
                justifyContent: 'center',
                paddingVertical: 7,
              }}
            >
              <Text
                style={{
                  fontSize: 12,
                  fontWeight: '900',
                  color: palette.ink,
                  fontVariant: ['tabular-nums'],
                }}
              >
                {item}
              </Text>
              <Text
                numberOfLines={1}
                adjustsFontSizeToFit
                minimumFontScale={0.7}
                maxFontSizeMultiplier={1}
                style={{
                  fontSize: 9,
                  fontWeight: '800',
                  color: palette.muted,
                  textTransform: 'uppercase',
                }}
              >
                {index === 6 ? 'insígnia' : 'item'}
              </Text>
            </View>
          ))}
        </View>
        <Txt variant="tiny" style={{ marginTop: 8 }}>
          7 itens por temporada · free e passe
        </Txt>
      </Card>
      <Card onPress={() => nav.go('badges')}>
        <Row between>
          <Txt variant="h3">Insígnias</Txt>
          <Txt variant="tiny">3 espaços</Txt>
        </Row>
        <View style={{ flexDirection: 'row', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
          <Badge tone="lime">{seasonCode}</Badge>
          <Badge>FUNDADOR</Badge>
          <Badge tone="blue">MEDALHA PRATA</Badge>
        </View>
      </Card>
      <BtnRow>
        <Btn tone="primary" go="season-track">
          Ver trilha
        </Btn>
        <Btn tone="ghost" go="missions">
          Missões
        </Btn>
      </BtnRow>
      <Btn tone="ghost" go="retrospective">
        Retrospectiva da temporada
      </Btn>
      {days <= 3 ? (
        <Btn tone="ghost" go="season-closing">
          Fechamento da temporada
        </Btn>
      ) : null}
    </Page>
  );
}

function Node({
  item,
  done,
  current,
  milestone,
  track,
  onPress,
}: {
  item: number;
  done: boolean;
  current: boolean;
  milestone: boolean;
  track: string;
  onPress: () => void;
}) {
  const { palette } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`Nível ${item}`}
      style={({ pressed }) => ({
        width: '18%',
        minHeight: 54,
        borderRadius: 10,
        borderWidth: 1.5,
        borderStyle: done || current ? 'solid' : 'dashed',
        borderColor: current ? palette.lineStrong : palette.line,
        backgroundColor: current ? palette.lime : done ? palette.surface2 : palette.surface,
        opacity: (done || current ? 1 : 0.55) * (pressed ? 0.86 : 1),
        alignItems: 'center',
        justifyContent: 'center',
        paddingVertical: 7,
        gap: 2,
      })}
    >
      <Text
        maxFontSizeMultiplier={1.3}
        style={{
          fontSize: 12,
          fontWeight: '900',
          color: current ? '#F1F3F0' : palette.ink,
          fontVariant: ['tabular-nums'],
        }}
      >
        {item}
      </Text>
      <Text
        numberOfLines={1}
        adjustsFontSizeToFit
        minimumFontScale={0.7}
        maxFontSizeMultiplier={1}
        style={{
          fontSize: 9,
          fontWeight: '800',
          textTransform: 'uppercase',
          color: current ? '#F1F3F0' : palette.muted,
        }}
      >
        {milestone ? 'item' : done ? 'ok' : 'XP'}
      </Text>
      {milestone ? (
        <Text
          numberOfLines={1}
          adjustsFontSizeToFit
          minimumFontScale={0.65}
          maxFontSizeMultiplier={1}
          style={{
            fontSize: 9,
            fontWeight: '800',
            color: current ? '#17191B' : palette.limeDeep,
          }}
        >
          {item === 30 ? 'insígnia' : track === 'pass' ? 'passe' : 'free'}
        </Text>
      ) : null}
    </Pressable>
  );
}

function SeasonTrack() {
  const nav = useNav();
  const { palette } = useTheme();
  const { track, xp, level, tier, percent, loaded, failed, retry } = useSeasonData();
  const levels = useMemo(() => {
    if (track?.levels.length) {
      return track.levels.map((item: TrackLevel) => ({
        level: item.level,
        item: item.item_name,
        track: item.track,
        xpRequired: item.xp_required,
        claimed: item.claimed,
        available: item.available,
        milestone: MILESTONES.includes(item.level),
      }));
    }
    return Array.from({ length: 30 }, (_, index) => {
      const n = index + 1;
      const definition = ITEM_DEFS.find(([itemLevel]) => itemLevel === n);
      return {
        level: n,
        item: definition?.[1] ?? null,
        track: definition?.[2] ?? 'free',
        xpRequired: n * 150,
        claimed: n < level,
        available: n === level,
        milestone: MILESTONES.includes(n),
      };
    });
  }, [track, level]);

  const openLevel = (levelNumber: number, itemTrack?: string, xpRequired?: number) => {
    if (levelNumber > level + 1) {
      nav.go('level-locked-xp', {
        level: levelNumber,
        xpRequired: xpRequired ?? levelNumber * 150,
      });
      return;
    }
    const definition = levels.find((item) => item.level === levelNumber);
    if (itemTrack === 'pass') {
      nav.go('item-locked-pass', {
        level: levelNumber,
        item: definition?.item ?? undefined,
      });
      return;
    }
    if (definition?.item) {
      nav.go('reward-claim', { level: levelNumber });
      return;
    }
    nav.toast(`Nível ${levelNumber} concluído.`);
  };

  if (!loaded) {
    return (
      <Page title="Trilha da temporada">
        <LoadingState label="Buscando a trilha da temporada." variant="track" />
      </Page>
    );
  }

  if (failed) {
    return (
      <Page title="Trilha da temporada">
        <StateScreen
          icon="wifi-off"
          title="Não foi possível carregar a trilha"
          text="Verifique a conexão e tente novamente. Seu progresso não foi alterado."
          actions={
            <Btn tone="primary" onPress={retry}>
              Tentar novamente
            </Btn>
          }
        />
      </Page>
    );
  }

  return (
    <Page title="Trilha da temporada">
      <Row between>
        <View>
          <Txt variant="label">Seu nível</Txt>
          <Txt variant="h2">
            {tier} {level}
          </Txt>
        </View>
        <Badge tone="lime">{number(xp)} XP</Badge>
      </Row>
      <Progress value={percent} tone="orange" />
      <Row between>
        <Txt variant="tiny">Nível 1</Txt>
        <Txt variant="tiny">30</Txt>
      </Row>
      <View
        style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 7, justifyContent: 'space-between' }}
      >
        {levels.map((item) => (
          <Node
            key={item.level}
            item={item.level}
            done={item.level < level}
            current={item.level === level}
            milestone={item.milestone}
            track={item.track}
            onPress={() =>
              openLevel(item.level, item.item ? item.track : undefined, item.xpRequired)
            }
          />
        ))}
      </View>
      <Row between>
        <Txt variant="h3">Itens da temporada</Txt>
        <Txt variant="tiny">7 itens</Txt>
      </Row>
      {levels
        .filter((item) => item.item)
        .map((item) => (
          <Pressable
            key={item.level}
            onPress={() => openLevel(item.level, item.track, item.xpRequired)}
            accessibilityRole="button"
            accessibilityLabel={`Item do nível ${item.level}`}
            style={({ pressed }) => ({
              flexDirection: 'row',
              gap: 10,
              alignItems: 'center',
              borderWidth: 1.5,
              borderColor: palette.line,
              borderRadius: 12,
              padding: 10,
              backgroundColor: pressed ? palette.surface2 : palette.surface,
              opacity: item.level > level + 1 ? 0.6 : 1,
            })}
          >
            <View
              style={{
                width: 34,
                height: 34,
                borderRadius: 8,
                backgroundColor: item.track === 'pass' ? palette.blue : palette.ink,
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Text
                maxFontSizeMultiplier={1.3}
                style={{ fontSize: 12, fontWeight: '900', color: palette.onInk }}
              >
                {item.level}
              </Text>
            </View>
            <View style={{ flex: 1 }}>
              <Text
                maxFontSizeMultiplier={1.3}
                style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}
              >
                {item.item}
              </Text>
              <Text maxFontSizeMultiplier={1.3} style={{ fontSize: 13, color: palette.muted }}>
                {item.track === 'pass'
                  ? 'Trilha do passe · empréstimo'
                  : 'Trilha free · permanente'}{' '}
                · {item.level > level + 1 ? 'bloqueado por XP' : 'disponível'}
              </Text>
            </View>
            <Badge tone={item.track === 'pass' ? 'blue' : 'lime'}>
              {item.track === 'pass' ? 'PASSE' : 'FREE'}
            </Badge>
            <Text style={{ color: palette.muted }}>›</Text>
          </Pressable>
        ))}
      <Notice tone="blue" icon="info">
        Ingressos grátis caem nos níveis 5, 10, 15, 20, 25 e 30. O XP é igual para todos.
      </Notice>
    </Page>
  );
}

function RewardClaim() {
  const nav = useNav();
  const { session, track, loadSeason } = useApp();
  const paramLevel = typeof nav.params.level === 'number' ? nav.params.level : null;
  const availableLevel = track?.levels.find((item) => item.available)?.level;
  const level = paramLevel ?? availableLevel ?? 24;
  const trackItem = track?.levels.find((item) => item.level === level);
  const definition = ITEM_DEFS.find(([itemLevel]) => itemLevel === level);
  const itemName = trackItem?.item_name ?? definition?.[1] ?? 'Recompensa';
  const itemTrack = trackItem?.track ?? definition?.[2] ?? 'free';
  const [busy, setBusy] = useState(false);
  const claim = async () => {
    setBusy(true);
    if (session) {
      try {
        await api.progress.claim(session.accessToken, level);
        await loadSeason();
      } catch {
        nav.toast('Não foi possível resgatar agora.');
        setBusy(false);
        return;
      }
    }
    setBusy(false);
    nav.replace('reward-claimed');
  };
  return (
    <Page title="Recompensa">
      <Card tone="lime" style={{ alignItems: 'center', padding: 22 }}>
        <Badge tone="lime">NÍVEL {level}</Badge>
        <Txt variant="display" style={{ fontSize: 30, marginTop: 10, marginBottom: 4 }}>
          {itemName}
        </Txt>
        <Txt variant="tiny">Item de temporada · {itemTrack === 'pass' ? 'passe' : 'free'}</Txt>
      </Card>
      <Card>
        <Kv label="Tipo" value={itemName} />
        <Kv label="Origem" value={itemTrack === 'pass' ? 'Trilha do passe' : 'Trilha free'} />
        <Kv label="Estado" value="Disponível para resgate" />
        <Kv label="Expira" value="Fim da temporada" />
      </Card>
      <Notice tone="blue" icon="info">
        Itens free são creditados automaticamente no fechamento; itens de passe exigem resgate
        manual.
      </Notice>
      <Btn tone="primary" onPress={claim} disabled={busy}>
        {busy ? 'Resgatando…' : 'Resgatar recompensa'}
      </Btn>
    </Page>
  );
}

function RewardClaimed() {
  return (
    <Page title="Recompensa">
      <StateScreen
        icon="check"
        title="Recompensa resgatada"
        text="A recompensa foi para o seu inventário. Você pode equipar agora ou deixar para depois."
        actions={
          <>
            <Btn tone="primary" go="inventory">
              Equipar agora
            </Btn>
            <Btn tone="ghost" go="inventory">
              Ver inventário
            </Btn>
          </>
        }
      />
    </Page>
  );
}

function LevelLockedXp() {
  const nav = useNav();
  const { progress } = useApp();
  const level = typeof nav.params.level === 'number' ? nav.params.level : 25;
  const xpRequired =
    typeof nav.params.xpRequired === 'number' ? nav.params.xpRequired : level * 150;
  const xp = progress?.xp_total ?? 0;
  const missing = Math.max(0, xpRequired - xp);
  const percent = Math.min(100, Math.round((xp / Math.max(1, xpRequired)) * 100));
  return (
    <Page title={`Nível ${level}`}>
      <StateScreen
        icon="lock"
        title={`Faltam ${number(missing)} XP`}
        text={`O nível ${level} abre com ${number(xpRequired)} XP. Jogue partidas, complete missões e visite quadras novas. O passe não acelera o XP.`}
        actions={
          <>
            <Btn tone="primary" go="queue-casual">
              Jogar para ganhar XP
            </Btn>
            <Btn tone="ghost" go="missions">
              Ver missões
            </Btn>
          </>
        }
      />
      <Progress value={percent} tone="orange" />
    </Page>
  );
}

function ItemLockedPass() {
  const nav = useNav();
  const item = typeof nav.params.item === 'string' ? nav.params.item : 'Item de lobby';
  return (
    <Page title="Item do passe">
      <StateScreen
        icon="lock"
        title="Item do passe"
        text={`${item} é um item de empréstimo do passe. Sem ciclo pago ativo, ele fica bloqueado. Itens conquistados por XP continuam seus.`}
        actions={
          <>
            <Btn tone="primary" go="pass">
              Conhecer o passe
            </Btn>
            <Btn tone="ghost" back>
              Continuar free
            </Btn>
          </>
        }
      />
    </Page>
  );
}

function Missions() {
  const { missions, loadSeason } = useApp();
  useEffect(() => {
    loadSeason().catch(() => undefined);
  }, [loadSeason]);
  const list = missions.map((item) => ({
    name:
      item.code === 'play_one'
        ? 'Jogar 1 partida'
        : item.code === 'new_venue'
          ? 'Jogar em uma quadra nova'
          : item.code === 'on_time_checkin'
            ? 'Check-in até o horário de início'
            : item.code,
    progress: `${item.progress}/${item.target}`,
    xp: `+${item.xp_reward} XP`,
    done: item.completed,
    percent: Math.min(100, Math.round((item.progress / Math.max(1, item.target)) * 100)),
  }));
  const done = list.filter((item) => item.done).length;
  return (
    <Page title="Missões da semana">
      <Row between>
        <Txt variant="tiny">Reset segunda · 00:00</Txt>
        <Badge tone="lime">
          {done} DE {list.length}
        </Badge>
      </Row>
      {list.map((item) => (
        <Card key={item.name} tone={item.done ? 'lime' : 'surface'}>
          <Row between>
            <Txt variant="h3">{item.name}</Txt>
            <Badge tone={item.done ? 'lime' : 'default'}>
              {item.done ? 'CONCLUÍDA' : 'EM ABERTO'}
            </Badge>
          </Row>
          <Row between style={{ marginTop: 8 }}>
            <Txt variant="tiny">{item.progress}</Txt>
            <Txt variant="tiny">{item.xp}</Txt>
          </Row>
          <View style={{ marginTop: 7 }}>
            <Progress value={item.percent} />
          </View>
        </Card>
      ))}
      <Notice tone="blue" icon="info">
        Missão não concluída não penaliza, não expira saldo e não gera dívida.
      </Notice>
    </Page>
  );
}

function Streak() {
  const { progress } = useApp();
  return (
    <Page title="Streak">
      <Card tone="ink" style={{ alignItems: 'center', padding: 22 }}>
        <Txt variant="display" color="onInk" style={{ fontSize: 58 }}>
          {progress?.streak.current ?? 0}
        </Txt>
        <Txt variant="tiny" color="softOnInk">
          vitórias seguidas
        </Txt>
        <Badge tone="lime">VÁLIDA ATÉ DOMINGO</Badge>
      </Card>
      <Card>
        <Kv label="Recorde" value={`${progress?.streak.best ?? 0} vitórias`} />
        <Kv label="Última vitória" value="—" />
        <Kv label="Próxima semana" value="sem partida zera" />
        <Kv label="XP por streak" value="não concede" />
      </Card>
      <Notice tone="orange" icon="info">
        Empate, derrota ou semana sem partida concluída zeram a sequência. O recorde nunca diminui.
      </Notice>
    </Page>
  );
}

function Badges() {
  const { palette } = useTheme();
  const { badges, loadSeason } = useApp();
  useEffect(() => {
    loadSeason().catch(() => undefined);
  }, [loadSeason]);
  const badgeNames = badges.map((item) => ({
    name: item.name,
    sub: item.kind,
    equipped: item.equipped_slot !== null,
  }));
  const equipped = badgeNames.filter((item) => item.equipped);
  return (
    <Page title="Insígnias e medalhas">
      <Card>
        <Row between>
          <Txt variant="h3">Equipadas</Txt>
          <Txt variant="tiny">3 espaços</Txt>
        </Row>
        <View style={{ flexDirection: 'row', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
          {equipped.length ? (
            equipped.map((item) => (
              <Badge key={item.name} tone="lime">
                {item.name.toUpperCase()}
              </Badge>
            ))
          ) : (
            <Txt variant="tiny">Nenhuma insígnia equipada.</Txt>
          )}
        </View>
        <Txt variant="tiny" style={{ marginTop: 8 }}>
          A insígnia da temporada é emitida no fechamento e não volta.
        </Txt>
      </Card>
      <Card>
        <Row between>
          <Txt variant="h3">Insígnias</Txt>
          <Badge>{badgeNames.length}</Badge>
        </Row>
        <View style={{ marginTop: 6 }}>
          {badgeNames.length ? (
            badgeNames.map((item, index) => (
              <View
                key={item.name}
                style={{
                  flexDirection: 'row',
                  alignItems: 'center',
                  gap: 10,
                  paddingVertical: 11,
                  borderBottomWidth: index === badgeNames.length - 1 ? 0 : 1,
                  borderBottomColor: palette.line,
                }}
              >
                <Badge tone="lime">{item.name.slice(0, 12).toUpperCase()}</Badge>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                    {item.name}
                  </Text>
                  <Text style={{ fontSize: 13, color: palette.muted }}>{item.sub}</Text>
                </View>
                <Text style={{ color: palette.ink }}>✓</Text>
              </View>
            ))
          ) : (
            <Txt variant="tiny">Nenhuma insígnia ainda.</Txt>
          )}
        </View>
      </Card>
      <Card>
        <Row between>
          <Txt variant="h3">Medalhas</Txt>
          <Badge tone="blue">0</Badge>
        </Row>
        <Txt variant="tiny" style={{ marginTop: 8 }}>
          Nenhuma medalha ainda.
        </Txt>
      </Card>
      <Btn tone="ghost" go="inventory">
        Equipar insígnia
      </Btn>
    </Page>
  );
}

function Inventory() {
  const { palette } = useTheme();
  return (
    <Page title="Inventário">
      <ChipRow>
        <Chip on>Todos</Chip>
        <Chip>Free</Chip>
        <Chip>XP</Chip>
        <Chip>Passe</Chip>
      </ChipRow>
      <CardList>
        {[
          ['Moldura Ouro', 'XP · nível 24', 'EQUIPADA', 'default'],
          ['Animação de lobby', 'Passe · empréstimo', 'EQUIPADA', 'blue'],
          ['Emote “boa jogada”', 'XP · nível 12', 'DISPONÍVEL', 'default'],
          ['Tema alto contraste', 'Free', 'EQUIPADA', 'green'],
          ['Efeito de perfil', 'Passe · revogado', 'HISTÓRICO', 'red'],
        ].map(([name, sub, status, tone], index, all) => (
          <ListRow key={name} last={index === all.length - 1}>
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>{name}</Text>
              <Text style={{ fontSize: 13, color: palette.muted }}>{sub}</Text>
            </View>
            <Badge tone={tone as 'default' | 'blue' | 'green' | 'red'}>{status}</Badge>
          </ListRow>
        ))}
      </CardList>
      <Notice tone="blue" icon="info">
        Item de passe revogado não apaga o histórico: ele pode voltar se você reassinar.
      </Notice>
      <Btn tone="primary" toast="Loadout aberto no protótipo">
        Editar loadout
      </Btn>
    </Page>
  );
}

function Retrospective() {
  return (
    <Page title="Retrospectiva 2026-Q4">
      <Card tone="ink">
        <Badge tone="lime">SEU TRIMESTRE</Badge>
        <Txt
          variant="display"
          color="onInk"
          style={{ fontSize: 30, marginTop: 10, marginBottom: 4 }}
        >
          42 partidas.{'\n'}24 vitórias.
        </Txt>
        <Txt variant="tiny" color="softOnInk">
          Você terminou em Platina IV e subiu 2 divisões.
        </Txt>
      </Card>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
        {[
          ['7', 'quadras novas'],
          ['6', 'melhor streak'],
          ['20h', 'horário favorito'],
          ['5x5', 'formato favorito'],
        ].map(([value, label]) => (
          <Card key={label} style={{ width: '47%' }} padding={12}>
            <Txt variant="num" align="center" style={{ fontSize: 26 }}>
              {value}
            </Txt>
            <Txt variant="tiny" align="center">
              {label}
            </Txt>
          </Card>
        ))}
      </View>
      <Card>
        <Txt variant="h3">Quadras que entraram no passaporte</Txt>
        <View style={{ flexDirection: 'row', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
          <Badge>ARENA SUL</Badge>
          <Badge>ARENA NORTE</Badge>
          <Badge>CLUBE OESTE</Badge>
          <Badge tone="blue">+4</Badge>
        </View>
      </Card>
      <Btn tone="ghost" modal="share">
        Compartilhar retrospectiva
      </Btn>
    </Page>
  );
}

function SeasonClosing() {
  return (
    <Page title="Fim de temporada">
      <StateScreen
        icon="clock"
        title="Temporada em fechamento"
        text="Faltam 3 dias. Resgate as recompensas pendentes. Itens free são creditados automaticamente; itens de passe não reclamados são perdidos."
        actions={
          <>
            <Btn tone="primary" go="season-track">
              Resgatar pendentes
            </Btn>
            <Btn tone="ghost" go="retrospective">
              Ver retrospectiva
            </Btn>
          </>
        }
      />
      <Card>
        <Kv label="Pendentes" value="2 recompensas" />
        <Kv label="Ingressos grátis" value="1 · expira no fim" />
        <Kv label="Insígnia" value="emitida no fechamento" />
      </Card>
    </Page>
  );
}

function SeasonEnded() {
  return (
    <Page title="Temporada encerrada">
      <StateScreen
        icon="trophy"
        title="2026-Q4 encerrada"
        text="Você terminou no nível Ouro 23 e na divisão Platina IV. A nova temporada começa em 01 dez. O nível e a divisão são recalculados; streak e itens permanentes ficam."
        actions={
          <>
            <Btn tone="primary" go="retrospective">
              Ver retrospectiva
            </Btn>
            <Btn tone="ghost" go="season">
              Ver nova temporada
            </Btn>
          </>
        }
      />
      <Card>
        <Kv label="Nível final" value="Ouro 23" />
        <Kv label="Divisão final" value="Platina IV" />
        <Kv label="Insígnia" value="2026-Q4 emitida" />
        <Kv label="Próxima temporada" value="2027-Q1 · 01 dez" />
      </Card>
    </Page>
  );
}

export const seasonScreens: ScreenDef[] = [
  { id: 'season', tab: 'temporada', render: () => <Season /> },
  { id: 'season-track', tab: 'temporada', render: () => <SeasonTrack /> },
  { id: 'reward-claim', tab: 'temporada', render: () => <RewardClaim /> },
  { id: 'reward-claimed', tab: 'temporada', render: () => <RewardClaimed /> },
  { id: 'level-locked-xp', tab: 'temporada', render: () => <LevelLockedXp /> },
  { id: 'item-locked-pass', tab: 'temporada', render: () => <ItemLockedPass /> },
  { id: 'missions', tab: 'temporada', render: () => <Missions /> },
  { id: 'streak', tab: 'temporada', render: () => <Streak /> },
  { id: 'badges', tab: 'temporada', render: () => <Badges /> },
  { id: 'inventory', tab: 'temporada', render: () => <Inventory /> },
  { id: 'retrospective', tab: 'temporada', render: () => <Retrospective /> },
  { id: 'season-closing', tab: 'temporada', render: () => <SeasonClosing /> },
  { id: 'season-ended', tab: 'temporada', render: () => <SeasonEnded /> },
];
