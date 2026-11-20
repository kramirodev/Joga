import { useEffect, useState } from 'react';
import { View } from 'react-native';

import { api } from '../api/client';
import type { CourtHistory, Passport } from '../api/types';
import { useApp } from '../state/app';
import { useTheme, useNav } from '../state/context';
import {
  Badge,
  Btn,
  BtnRow,
  Card,
  CardList,
  ChipRow,
  EmptyState,
  HeatGrid,
  Kv,
  ListRow,
  Meter,
  Notice,
  Page,
  Photo,
  PhotoCap,
  Progress,
  Row,
  StateScreen,
  TextBtn,
  Txt,
} from '../ui/kit';
import { divisionLabel } from '../ui/datetime';
import { Text } from '../ui/text';
import type { ScreenDef } from './types';

function Stats() {
  const { palette } = useTheme();
  const nav = useNav();
  const { network, loadStats } = useApp();
  useEffect(() => {
    loadStats().catch(() => undefined);
  }, [loadStats]);
  const venues = (network?.venues ?? []).slice(0, 2).map((item) => ({
    name: item.name,
    sub: `${item.level.toLowerCase()} · ${item.matches} partidas`,
    level: item.level,
  }));
  const hasPass = network?.has_pass ?? false;
  return (
    <Page title="Rede">
      <Card tone="ink">
        <Row between>
          <Badge tone="lime">DADOS DO APP</Badge>
          <Badge>ATUALIZAÇÃO DIÁRIA</Badge>
        </Row>
        <Txt
          variant="display"
          color="onInk"
          style={{ fontSize: 28, marginTop: 10, marginBottom: 4 }}
        >
          Onde o jogo{'\n'}acontece.
        </Txt>
        <Txt variant="tiny" color="softOnInk">
          Agregado, em faixas. Nenhum jogador é identificado.
        </Txt>
      </Card>
      <Card>
        <Row between>
          <Txt variant="h3">Quadras mais usadas</Txt>
          <Badge tone="green">GRÁTIS</Badge>
        </Row>
        <View style={{ marginTop: 6 }}>
          {venues.length ? (
            venues.map((item, index) => (
              <View
                key={item.name}
                style={{
                  flexDirection: 'row',
                  alignItems: 'center',
                  gap: 10,
                  paddingVertical: 11,
                  borderBottomWidth: index === venues.length - 1 ? 0 : 1,
                  borderBottomColor: palette.line,
                }}
              >
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                    {item.name}
                  </Text>
                  <Text style={{ fontSize: 13, color: palette.muted }}>{item.sub}</Text>
                </View>
                <Badge tone={item.level === 'ALTA' ? 'orange' : 'default'}>{item.level}</Badge>
              </View>
            ))
          ) : (
            <Txt variant="tiny">Nenhuma quadra com amostra suficiente.</Txt>
          )}
        </View>
      </Card>
      <Card>
        <Row between>
          <Txt variant="h3">Movimento da semana</Txt>
          <Badge tone="blue">PASSE</Badge>
        </Row>
        {hasPass ? (
          <>
            <View style={{ marginTop: 10 }}>
              <HeatGrid />
            </View>
            <Txt variant="tiny" style={{ marginTop: 6 }}>
              Dia × faixa horária. Atualizado diariamente.
            </Txt>
          </>
        ) : (
          <Txt variant="tiny" style={{ marginTop: 8 }}>
            Disponível no passe.
          </Txt>
        )}
      </Card>
      <Card>
        <Row between>
          <Txt variant="h3">Onde o jogo é mais forte</Txt>
          <Badge tone="blue">PASSE</Badge>
        </Row>
        {hasPass && venues.length ? (
          venues.map((item, index) => (
            <Row key={item.name} between style={{ marginTop: index === 0 ? 8 : 6 }}>
              <Txt variant="tiny">{item.name}</Txt>
              <Badge tone="blue">{item.level}</Badge>
            </Row>
          ))
        ) : (
          <Txt variant="tiny" style={{ marginTop: 8 }}>
            Disponível no passe.
          </Txt>
        )}
      </Card>
      <Notice tone="blue" icon="info">
        Plano gratuito vê a lista de quadras e os horários com mais vaga; o passe vê mapa, densidade
        e ocupação.
      </Notice>
      <BtnRow>
        <Btn tone="primary" onPress={() => nav.go(hasPass ? 'network' : 'stats-locked')}>
          Ver painel completo
        </Btn>
        <Btn tone="ghost" go="support">
          Entender regras
        </Btn>
      </BtnRow>
    </Page>
  );
}

function StatsEvolution() {
  const nav = useNav();
  const { ratings, primaryFormatId, profile } = useApp();
  const rating = primaryFormatId ? ratings[primaryFormatId] : undefined;
  if (!rating || rating.matches_played === 0) {
    return (
      <Page title="Minha evolução">
        <EmptyState
          title="Sem partidas ranqueadas"
          text="Sua evolução aparece depois das primeiras partidas ranqueadas."
          actions={
            <Btn tone="primary" icon="search" onPress={() => nav.go('queue', { mode: 'ranked' })}>
              Buscar ranqueada
            </Btn>
          }
        />
      </Page>
    );
  }
  return (
    <Page title="Minha evolução">
      <Row between>
        <Badge tone="blue">PASSE</Badge>
        <Badge>ATUALIZAÇÃO DIÁRIA</Badge>
      </Row>
      <Card>
        <Kv
          label="Divisão atual"
          value={`${divisionLabel(rating.division)} · ${Math.round((rating.progress ?? 0) * 100)}%`}
        />
        <Kv label="Partidas" value={String(rating.matches_played)} />
        <Kv label="Posição" value={rating.position ? `#${rating.position}` : '—'} />
        <Kv label="Formato" value={profile?.sports[0]?.format_name ?? '—'} />
      </Card>
    </Page>
  );
}

function StatsVenues() {
  const { session, stats, loadStats } = useApp();
  const [courts, setCourts] = useState<CourtHistory[]>([]);
  useEffect(() => {
    loadStats().catch(() => undefined);
    if (session) {
      api.stats
        .courts(session.accessToken)
        .then((result) => setCourts(result.courts))
        .catch(() => undefined);
    }
  }, [session, loadStats]);
  if (stats && !stats.has_pass) {
    return (
      <Page title="Minhas quadras">
        <StateScreen
          icon="lock"
          title="Histórico por quadra é do passe"
          text="A evolução, o passaporte e o histórico por quadra fazem parte do passe."
          actions={
            <>
              <Btn tone="primary" go="pass">
                Conhecer o passe
              </Btn>
              <Btn tone="ghost" go="profile-me">
                Voltar ao perfil
              </Btn>
            </>
          }
        />
      </Page>
    );
  }
  const rows = courts.map((court) => ({
    name: court.name,
    matches: `${court.matches} partidas`,
    record:
      court.matches < 20 ? 'amostra pequena' : `${court.wins}V · ${court.matches - court.wins}D`,
    time: court.last_played_at ? court.last_played_at.slice(11, 16) : '—',
  }));
  return (
    <Page title="Minhas quadras">
      {rows.length ? (
        <CardList>
          {rows.map((row, index) => (
            <ListRow key={row.name} last={index === rows.length - 1}>
              <View style={{ flex: 1 }}>
                <Row between>
                  <Text style={{ fontSize: 14, fontWeight: '800' }}>{row.name}</Text>
                  <Txt variant="tiny">{row.time}</Txt>
                </Row>
                <Txt variant="tiny">
                  {row.matches} · {row.record}
                </Txt>
              </View>
              {row.record.includes('pequena') ? (
                <Badge tone="orange">AMOSTRA PEQUENA</Badge>
              ) : (
                <Badge tone="green">OK</Badge>
              )}
            </ListRow>
          ))}
        </CardList>
      ) : (
        <EmptyState
          title="Nenhuma quadra no histórico"
          text="Partidas concluídas em quadras aparecem aqui."
        />
      )}
      <Notice tone="orange" icon="info">
        Abaixo de 20 partidas, o histórico mostra “amostra pequena” em vez de aproveitamento.
      </Notice>
    </Page>
  );
}

function StatsPassport() {
  const { palette } = useTheme();
  const { session, stats, loadStats } = useApp();
  const [passport, setPassport] = useState<Passport | null>(null);
  const [courts, setCourts] = useState<CourtHistory[]>([]);
  useEffect(() => {
    loadStats().catch(() => undefined);
    if (session) {
      api.stats
        .passport(session.accessToken)
        .then(setPassport)
        .catch(() => undefined);
      api.stats
        .courts(session.accessToken)
        .then((result) => setCourts(result.courts))
        .catch(() => undefined);
    }
  }, [session, loadStats]);
  if (stats && !stats.has_pass) {
    return (
      <Page title="Meu passaporte">
        <StateScreen
          icon="lock"
          title="Passaporte é do passe"
          text="O passaporte de quadras e as estatísticas avançadas fazem parte do passe."
          actions={
            <>
              <Btn tone="primary" go="pass">
                Conhecer o passe
              </Btn>
              <Btn tone="ghost" go="profile-me">
                Voltar ao perfil
              </Btn>
            </>
          }
        />
      </Page>
    );
  }
  const visited = passport?.courts ?? 0;
  return (
    <Page title="Meu passaporte">
      <Card tone="ink">
        <Badge tone="lime">{visited} DE 30</Badge>
        <Txt
          variant="display"
          color="onInk"
          style={{ fontSize: 30, marginTop: 10, marginBottom: 4 }}
        >
          Você já jogou{'\n'}em {visited} quadras.
        </Txt>
        <Progress value={(visited / 30) * 100} tone="blue" />
      </Card>
      <Photo tone="blue">
        <PhotoCap badge={<Badge>{visited} PINOS</Badge>}>
          Quadras visitadas · endereço exato
        </PhotoCap>
      </Photo>
      {courts.length ? (
        <CardList>
          {courts.slice(0, 3).map((court, index, all) => (
            <ListRow key={court.name} last={index === all.length - 1}>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                  {court.name}
                </Text>
                <Text style={{ fontSize: 13, color: palette.muted }}>
                  {`${court.matches} partidas`}
                </Text>
              </View>
              <Txt variant="tiny">
                {court.last_played_at ? court.last_played_at.slice(0, 10) : '—'}
              </Txt>
            </ListRow>
          ))}
        </CardList>
      ) : (
        <EmptyState
          title="Nenhuma quadra visitada"
          text="Seu passaporte começa na primeira partida concluída."
        />
      )}
    </Page>
  );
}

function StatsTimes() {
  const nav = useNav();
  const { palette } = useTheme();
  const { stats } = useApp();
  if (!stats || stats.totals.matches === 0) {
    return (
      <Page title="Meus horários">
        <EmptyState
          title="Sem partidas suficientes"
          text="Seus horários e formatos aparecem depois das primeiras partidas."
          actions={
            <Btn tone="primary" icon="search" onPress={() => nav.go('queue', { mode: 'casual' })}>
              Buscar partida
            </Btn>
          }
        />
      </Page>
    );
  }
  const formats = stats.by_format.map((item) => ({
    name: item.name,
    percent: stats.totals.matches ? Math.round((item.matches / stats.totals.matches) * 100) : 0,
    value: item.matches,
  }));
  return (
    <Page title="Meus horários">
      <Card>
        <Txt variant="h3">Formatos</Txt>
        <View style={{ marginTop: 10, gap: 8 }}>
          {formats.map((format) => (
            <View key={format.name} style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <Text style={{ width: 76, fontSize: 12, color: palette.muted, fontWeight: '700' }}>
                {format.name}
              </Text>
              <View
                style={{
                  flex: 1,
                  height: 14,
                  backgroundColor: palette.progressTrack,
                  borderRadius: 3,
                  overflow: 'hidden',
                }}
              >
                <View
                  style={{
                    height: '100%',
                    width: `${format.percent}%`,
                    backgroundColor: palette.lime,
                  }}
                />
              </View>
              <Text
                style={{
                  width: 30,
                  textAlign: 'right',
                  fontSize: 12,
                  fontWeight: '800',
                  color: palette.ink,
                }}
              >
                {format.value}
              </Text>
            </View>
          ))}
        </View>
      </Card>
    </Page>
  );
}

function Network() {
  const { palette } = useTheme();
  const { network, loadStats } = useApp();
  useEffect(() => {
    loadStats().catch(() => undefined);
  }, [loadStats]);
  if (network && !network.has_pass) {
    return (
      <Page title="Rede">
        <StateScreen
          icon="lock"
          title="Painel completo do passe"
          text="Mapa, densidade e ocupação são do passe. A lista de quadras e os horários com mais vaga continuam livres."
          actions={
            <>
              <Btn tone="primary" go="pass">
                Conhecer o passe
              </Btn>
              <Btn tone="ghost" go="stats">
                Voltar à rede
              </Btn>
            </>
          }
        />
      </Page>
    );
  }
  const venues = (network?.venues ?? []).slice(0, 3).map((item) => ({
    name: item.name,
    sub: `${item.matches} partidas`,
    level: item.level.toUpperCase(),
  }));
  const occupancy = (network?.cells ?? []).slice(0, 3).map((cell) => ({
    name: cell.space_name,
    level: cell.level.toUpperCase(),
    value: cell.level === 'alta' ? 4 : cell.level === 'média' ? 3 : 2,
    tone: (cell.level === 'alta' ? 'orange' : cell.level === 'média' ? 'default' : 'green') as
      'orange' | 'default' | 'green',
  }));
  return (
    <Page title="Inteligência de rede">
      <Row between>
        <Badge tone="blue">PASSE</Badge>
        <Badge>ATUALIZAÇÃO DIÁRIA</Badge>
      </Row>
      <ChipRow>
        <Badge tone="lime">MAPA</Badge>
        <Badge>QUADRAS</Badge>
        <Badge>DENSIDADE</Badge>
        <Badge>OCUPAÇÃO</Badge>
      </ChipRow>
      <Card>
        <Row between>
          <Txt variant="h3">Movimento da rede</Txt>
          <Badge>SEMANA</Badge>
        </Row>
        <Txt variant="tiny" style={{ marginTop: 10 }}>
          {network?.peak_band
            ? `Pico de movimento: ${network.peak_band}`
            : 'Sem amostra suficiente para exibir o movimento.'}
        </Txt>
        <Txt variant="tiny" style={{ marginTop: 8 }}>
          {network
            ? `${network.sample_size} partidas na amostra de ${network.window_days} dias.`
            : ''}
        </Txt>
      </Card>
      <Card>
        <Txt variant="h3">Quadras mais usadas</Txt>
        <View style={{ marginTop: 6 }}>
          {venues.length ? (
            venues.map((item, index) => (
              <View
                key={item.name}
                style={{
                  flexDirection: 'row',
                  alignItems: 'center',
                  gap: 10,
                  paddingVertical: 11,
                  borderBottomWidth: index === venues.length - 1 ? 0 : 1,
                  borderBottomColor: palette.line,
                }}
              >
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                    {item.name}
                  </Text>
                  <Text style={{ fontSize: 13, color: palette.muted }}>{item.sub}</Text>
                </View>
                <Badge tone={item.level === 'ALTA' ? 'orange' : 'default'}>{item.level}</Badge>
              </View>
            ))
          ) : (
            <Txt variant="tiny">Nenhuma quadra com amostra suficiente.</Txt>
          )}
        </View>
      </Card>
      <Card>
        <Txt variant="h3">Densidade competitiva</Txt>
        {venues.length ? (
          venues.map((item, index) => (
            <Row key={item.name} between style={{ marginTop: index === 0 ? 8 : 6 }}>
              <Txt variant="tiny">{item.name}</Txt>
              <Badge tone={item.level === 'ALTA' ? 'blue' : 'default'}>{item.level}</Badge>
            </Row>
          ))
        ) : (
          <Txt variant="tiny" style={{ marginTop: 8 }}>
            Sem amostra suficiente.
          </Txt>
        )}
        <Txt variant="tiny" style={{ marginTop: 8 }}>
          Faixas, nunca números. Não é filtro de matchmaking.
        </Txt>
      </Card>
      <Card>
        <Row between>
          <Txt variant="h3">Ocupação</Txt>
          <Badge>JANELA 30 DIAS</Badge>
        </Row>
        <View style={{ marginTop: 10, gap: 10 }}>
          {occupancy.length ? (
            occupancy.map((item) => (
              <View key={item.name}>
                <Row between style={{ marginBottom: 6 }}>
                  <Txt variant="tiny">{item.name}</Txt>
                  <Badge tone={item.tone}>{item.level}</Badge>
                </Row>
                <Meter value={item.value} />
              </View>
            ))
          ) : (
            <Txt variant="tiny">Sem células com amostra suficiente.</Txt>
          )}
        </View>
        <Txt variant="tiny" style={{ marginTop: 8 }}>
          Faixas de ocupação, não contagem de pessoas. Tendência sobe ou desce devagar, nunca em
          tempo real.
        </Txt>
      </Card>
      <Notice tone="orange" icon="shield">
        Células com menos de 20 partidas em 30 dias não aparecem.
      </Notice>
      <TextBtn go="network-sample" muted>
        Como funciona a amostra mínima
      </TextBtn>
    </Page>
  );
}

function NetworkSample() {
  return (
    <Page title="Rede">
      <StateScreen
        icon="lock"
        title="Amostra insuficiente"
        text="A Arena Nova teve 12 partidas em 30 dias. O painel exige 20 para exibir densidade e ocupação."
        actions={
          <>
            <Btn tone="primary" go="network">
              Ver outra quadra
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

function StatsLocked() {
  return (
    <Page title="Rede">
      <StateScreen
        icon="lock"
        title="Painel completo do passe"
        text="Mapa, densidade e ocupação são do passe. A lista de quadras e os horários com mais vaga continuam livres."
        actions={
          <>
            <Btn tone="primary" go="pass">
              Conhecer o passe
            </Btn>
            <Btn tone="ghost" go="stats">
              Voltar à rede
            </Btn>
          </>
        }
      />
    </Page>
  );
}

export const statsScreens: ScreenDef[] = [
  { id: 'stats', tab: 'jogar', render: () => <Stats /> },
  { id: 'stats-evolution', tab: 'perfil', render: () => <StatsEvolution /> },
  { id: 'stats-venues', tab: 'perfil', render: () => <StatsVenues /> },
  { id: 'stats-passport', tab: 'perfil', render: () => <StatsPassport /> },
  { id: 'stats-times', tab: 'perfil', render: () => <StatsTimes /> },
  { id: 'network', tab: 'jogar', render: () => <Network /> },
  { id: 'network-sample', tab: 'jogar', render: () => <NetworkSample /> },
  { id: 'stats-locked', tab: 'jogar', render: () => <StatsLocked /> },
];
