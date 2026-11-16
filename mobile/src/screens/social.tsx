import { useCallback, useEffect, useState } from 'react';
import { Text, View } from 'react-native';

import { api, ApiError } from '../api/client';
import type {
  ChatMessage,
  Clan,
  ClanMember,
  ModerationAction,
  ModerationReport,
  Notification,
} from '../api/types';
import { useApp } from '../state/app';
import { useNav, useTheme } from '../state/context';
import { Avatar } from '../ui/Avatar';
import { Icon } from '../ui/icons';
import {
  Badge,
  Btn,
  BtnRow,
  Card,
  CardList,
  Chip,
  ChipRow,
  EmptyState,
  Field,
  IconBtn,
  Input,
  Kv,
  ListRow,
  LoadingState,
  Notice,
  Page,
  Row,
  Seg,
  SegBtn,
  StateScreen,
  SystemNotice,
  Textarea,
  TextBtn,
  Txt,
} from '../ui/kit';
import { divisionLabel, number, shortDateTime } from '../ui/datetime';
import type { ScreenDef } from './types';

function toastError(nav: { toast: (message: string) => void }, error: unknown) {
  if (error instanceof ApiError) {
    const map: Record<string, string> = {
      network_unavailable: 'Não foi possível falar com o servidor.',
      clan_full: 'Clã cheio.',
      clan_cooldown: 'Aguarde antes de entrar em outro clã.',
      already_friends: 'Vocês já são amigos.',
      friend_request_exists: 'Solicitação já enviada.',
    };
    nav.toast(map[error.code] ?? 'Não foi possível concluir a ação.');
  } else {
    nav.toast('Não foi possível concluir a ação.');
  }
}

function Friends() {
  const nav = useNav();
  const { palette } = useTheme();
  const { friends, loadSocial } = useApp();
  const [tab, setTab] = useState('Amigos');
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    loadSocial()
      .catch(() => {
        if (active) {
          setFailed(true);
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [loadSocial]);
  const retry = () => {
    setLoading(true);
    setFailed(false);
    loadSocial()
      .catch(() => setFailed(true))
      .finally(() => setLoading(false));
  };
  const list = friends.map((friend) => ({
    id: friend.user_id,
    name: friend.display_name ?? 'Jogador',
    tag: '',
    meta: 'Amigo',
  }));
  return (
    <Page title="Amigos">
      <CardList>
        {[
          {
            icon: 'clan' as const,
            title: 'Meu clã',
            sub: 'Perfil, membros e chat do grupo',
            go: 'clan',
          },
          {
            icon: 'plus' as const,
            title: 'Descobrir clãs',
            sub: 'Entrar em um clã aberto ou criar o seu',
            go: 'clan-discovery',
          },
          {
            icon: 'trophy' as const,
            title: 'Ranking',
            sub: 'Sua posição individual por modalidade',
            go: 'ranking',
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
      {loading ? (
        <LoadingState label="Buscando seus amigos." variant="social" />
      ) : failed ? (
        <StateScreen
          icon="wifi-off"
          title="Não foi possível carregar seus amigos"
          text="Verifique a conexão e tente novamente. Seus convites continuam salvos."
          actions={
            <Btn tone="primary" onPress={retry}>
              Tentar novamente
            </Btn>
          }
        />
      ) : (
        <>
          <Seg>
            {['Amigos', 'Solicitações', 'Bloqueados'].map((item) => (
              <SegBtn key={item} on={tab === item} onPress={() => setTab(item)}>
                {item}
              </SegBtn>
            ))}
          </Seg>
          {tab === 'Amigos' ? (
            list.length ? (
              <CardList>
                {list.map((friend, index) => (
                  <ListRow
                    key={friend.id}
                    last={index === list.length - 1}
                    onPress={() =>
                      nav.go('profile-other', { userId: friend.id, name: friend.name })
                    }
                  >
                    <Avatar
                      size={34}
                      palette={palette}
                      skin="#A6ABB1"
                      hair="#17191B"
                      shirt="#62686E"
                      style={((index % 3) + 1) as 1 | 2 | 3}
                    />
                    <View style={{ flex: 1 }}>
                      <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                        {friend.name}{' '}
                      </Text>
                      <Text style={{ fontSize: 13, color: palette.muted }}>{friend.meta}</Text>
                    </View>
                    <Text style={{ color: palette.muted }}>›</Text>
                  </ListRow>
                ))}
              </CardList>
            ) : (
              <EmptyState
                title="Nenhum amigo ainda"
                text="Adicione amigos para convidar para lobbies."
              />
            )
          ) : (
            <Notice tone="blue" icon="info">
              {tab === 'Solicitações'
                ? 'Nenhuma solicitação pendente.'
                : 'Nenhum jogador bloqueado.'}
            </Notice>
          )}
        </>
      )}
      <Notice tone="blue" icon="shield">
        Convidar para lobby só é possível com amizade aceita e sem bloqueio.
      </Notice>
      <Btn tone="primary" icon="plus" go="add-friend">
        Adicionar amigo
      </Btn>
    </Page>
  );
}

function AddFriend() {
  const nav = useNav();
  const [query, setQuery] = useState('');
  const [searched, setSearched] = useState(false);
  const search = () => {
    if (query.trim().length < 3) {
      nav.toast('Digite pelo menos 3 caracteres, como nome#tag.');
      return;
    }
    setSearched(true);
  };
  return (
    <Page title="Adicionar amigo">
      <Txt variant="lead">
        Procure pelo nome de exibição e pela tag. O telefone nunca é usado como busca.
      </Txt>
      <Input
        value={query}
        onChangeText={setQuery}
        placeholder="nome#tag"
        maxLength={60}
        autoCorrect={false}
      />
      <Btn tone="primary" icon="search" onPress={search}>
        Buscar jogador
      </Btn>
      {searched ? (
        <Notice tone="blue" icon="search">
          {`Nenhum jogador encontrado para "${query.trim()}". Confira o nome#tag ou peça a tag ao jogador.`}
        </Notice>
      ) : (
        <Card tone="flat">
          <Txt variant="tiny">Digite nome#tag para buscar jogadores.</Txt>
        </Card>
      )}
    </Page>
  );
}

function ClanProfile() {
  const nav = useNav();
  const { palette } = useTheme();
  const { clan, clanMembers, clanMessages, loadClan } = useApp();
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    loadClan()
      .catch(() => undefined)
      .finally(() => setLoading(false));
  }, [loadClan]);
  if (loading) {
    return (
      <Page title="Clã">
        <LoadingState label="Buscando seu clã." variant="clan" />
      </Page>
    );
  }
  if (!clan) {
    return (
      <Page title="Clã">
        <EmptyState
          title="Você ainda não tem clã"
          text="Entre em um clã aberto ou crie o seu para jogar com o grupo."
          actions={
            <>
              <Btn tone="primary" go="clan-discovery">
                Descobrir clãs
              </Btn>
              <Btn tone="ghost" go="clan-create">
                Criar clã
              </Btn>
            </>
          }
        />
      </Page>
    );
  }
  return (
    <Page title={clan.name}>
      <Card tone="ink">
        <Row between>
          <Badge tone="lime">{clan.join_policy === 'open' ? 'ABERTO' : 'FECHADO'}</Badge>
          <Badge>
            {clan.members}/{clan.max_members}
          </Badge>
        </Row>
        <Row style={{ marginTop: 12 }}>
          <View
            style={{
              width: 64,
              height: 64,
              borderRadius: 32,
              backgroundColor: palette.lime,
              borderWidth: 1.5,
              borderColor: palette.lime,
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Icon name="clan" size={26} color="#F1F3F0" />
          </View>
          <View style={{ flex: 1 }}>
            <Txt variant="display" color="onInk" style={{ fontSize: 28 }}>
              {clan.name}
            </Txt>
            <Txt variant="tiny" color="softOnInk">
              {clan.tag} · {clan.members} de {clan.max_members} membros
            </Txt>
          </View>
        </Row>
        <View style={{ flexDirection: 'row', gap: 6, marginTop: 12, flexWrap: 'wrap' }}>
          <Badge>TROFÉUS {number(clan.trophies)}</Badge>
        </View>
      </Card>
      <Card>
        <Txt variant="h3">Sobre</Txt>
        <Txt variant="sub" style={{ marginTop: 5 }}>
          {clan.description ?? 'Sem descrição.'}
        </Txt>
      </Card>
      <View style={{ flexDirection: 'row', gap: 8 }}>
        <Card style={{ flex: 1 }} onPress={() => nav.go('clan-chat')}>
          <Icon name="chat" size={20} color={palette.ink} />
          <Txt variant="h3" style={{ marginTop: 6 }}>
            Chat
          </Txt>
          <Txt variant="tiny">{clanMessages.length} mensagens</Txt>
        </Card>
        <Card style={{ flex: 1 }} onPress={() => nav.go('clan-ranking')}>
          <Icon name="trophy" size={20} color={palette.ink} />
          <Txt variant="h3" style={{ marginTop: 6 }}>
            Troféus
          </Txt>
          <Txt variant="tiny">{number(clan.trophies)}</Txt>
        </Card>
      </View>
      <CardList>
        {[
          {
            icon: 'users' as const,
            title: 'Membros e cargos',
            sub: `${clanMembers.length || 24} membros · 3 oficiais`,
            go: 'clan-members',
          },
          {
            icon: 'gear' as const,
            title: 'Configurações do clã',
            sub: 'Identidade, entrada e escudo',
            go: 'clan-settings',
          },
          {
            icon: 'plus' as const,
            title: 'Convidar membros',
            sub: 'Amigos aceitos e sem bloqueio',
            go: 'clan-invite',
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
      <Notice tone="blue" icon="info">
        O escudo do clã é livre e aparece no perfil de todos. Só o destaque no perfil do clã é perk
        do passe.
      </Notice>
    </Page>
  );
}

function ClanDiscovery() {
  const nav = useNav();
  const { session, loadClan } = useApp();
  const [clans, setClans] = useState<Clan[]>([]);
  useEffect(() => {
    if (session) {
      api.clans
        .list(session.accessToken)
        .then((result) => setClans(result.clans))
        .catch(() => undefined);
    }
  }, [session]);
  const list = clans.map((clan) => ({
    id: clan.id,
    name: clan.name,
    tag: clan.tag,
    members: `${clan.members}/${clan.max_members}`,
    slots: Math.max(0, clan.max_members - clan.members),
    policy: clan.join_policy === 'open' ? 'ABERTO' : 'FECHADO',
    full: clan.members >= clan.max_members,
  }));
  const join = async (clanId: string, full: boolean) => {
    if (full) {
      nav.go('clan-full');
      return;
    }
    if (session) {
      try {
        await api.clans.join(session.accessToken, clanId);
        await loadClan();
        nav.replace('clan');
      } catch (error) {
        toastError(nav, error);
      }
      return;
    }
    nav.replace('clan');
  };
  return (
    <Page title="Descobrir clãs">
      <Input placeholder="Buscar clã ou tag" maxLength={60} />
      <ChipRow>
        <Chip on>Futebol 5x5</Chip>
        <Chip>Aberto</Chip>
        <Chip on>Com vaga</Chip>
      </ChipRow>
      {list.length ? (
        list.map((clan) => (
          <Card key={clan.id}>
            <Row between>
              <Badge tone={clan.policy === 'ABERTO' ? 'lime' : 'default'}>
                {clan.full ? 'CHEIO' : clan.policy}
              </Badge>
              <Txt variant="tiny">{clan.members}</Txt>
            </Row>
            <Txt variant="h2" style={{ marginTop: 6, marginBottom: 2 }}>
              {clan.name}
            </Txt>
            <Txt variant="tiny">{clan.tag}</Txt>
            <Row between style={{ marginTop: 12 }}>
              <Txt variant="tiny">
                {clan.full
                  ? 'sem vaga'
                  : clan.policy === 'FECHADO'
                    ? 'entrada por aprovação'
                    : `${clan.slots} vagas`}
              </Txt>
              <Btn
                tone={clan.full ? 'ghost' : clan.policy === 'ABERTO' ? 'primary' : 'ghost'}
                small
                block={false}
                onPress={() =>
                  clan.full
                    ? nav.go('clan-full')
                    : clan.policy === 'FECHADO'
                      ? nav.go('clan-join')
                      : join(clan.id, false)
                }
              >
                {clan.full ? 'Ver perfil' : clan.policy === 'ABERTO' ? 'Entrar' : 'Solicitar'}
              </Btn>
            </Row>
          </Card>
        ))
      ) : (
        <EmptyState
          title="Nenhum clã encontrado"
          text="Crie um clã ou ajuste a busca."
          actions={
            <Btn tone="primary" go="clan-create">
              Criar clã
            </Btn>
          }
        />
      )}
    </Page>
  );
}

function ClanCreate() {
  const nav = useNav();
  const { palette } = useTheme();
  const { session, loadClan } = useApp();
  const [name, setName] = useState('');
  const [tag, setTag] = useState('');
  const [description, setDescription] = useState('');
  const [policy, setPolicy] = useState('Aberto');
  const [shield, setShield] = useState(0);
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    if (!session) {
      nav.replace('clan');
      return;
    }
    setBusy(true);
    try {
      await api.clans.create(
        session.accessToken,
        name || 'Novo clã',
        tag || '#NOVO',
        description || null,
      );
      await loadClan();
      nav.replace('clan');
    } catch (error) {
      toastError(nav, error);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Page title="Criar clã">
      <Field label="Nome">
        <Input value={name} onChangeText={setName} maxLength={40} placeholder="Nome do clã" />
      </Field>
      <Field label="Tag">
        <Input value={tag} onChangeText={setTag} maxLength={8} placeholder="#TAG" />
      </Field>
      <Field label="Descrição">
        <Textarea
          value={description}
          onChangeText={setDescription}
          maxLength={280}
          placeholder="O que o clã joga e onde"
        />
      </Field>
      <Card>
        <Txt variant="h3">Escudo</Txt>
        <Txt variant="tiny" style={{ marginTop: 4, marginBottom: 10 }}>
          Catálogo fechado, sem upload.
        </Txt>
        <View style={{ flexDirection: 'row', gap: 8 }}>
          {['#E53935', '#62686E', '#62686E', '#E53935'].map((color, index) => (
            <View
              key={index}
              onTouchEnd={() => setShield(index)}
              style={{
                width: 52,
                height: 52,
                borderRadius: 26,
                backgroundColor: color,
                borderWidth: shield === index ? 2 : 1.5,
                borderColor: shield === index ? '#17191B' : palette.line,
              }}
            />
          ))}
        </View>
      </Card>
      <Field label="Entrada">
        <Seg>
          {['Aberto', 'Fechado'].map((item) => (
            <SegBtn key={item} on={policy === item} onPress={() => setPolicy(item)}>
              {item}
            </SegBtn>
          ))}
        </Seg>
      </Field>
      <Notice tone="blue" icon="info">
        Clã fechado depende de convite ou aprovação de administrador.
      </Notice>
      <Btn tone="primary" onPress={submit} disabled={busy}>
        {busy ? 'Criando…' : 'Criar clã'}
      </Btn>
    </Page>
  );
}

function ClanJoin() {
  return (
    <Page title="Quadra 9">
      <Card tone="ink">
        <Row between>
          <Badge>FECHADO</Badge>
          <Badge>30/30</Badge>
        </Row>
        <Txt
          variant="display"
          color="onInk"
          style={{ fontSize: 28, marginTop: 10, marginBottom: 4 }}
        >
          Quadra 9
        </Txt>
        <Txt variant="tiny" color="softOnInk">
          #Q9 · vôlei 6x6 · top 8
        </Txt>
      </Card>
      <Card>
        <Kv label="Membros" value="30 de 30" />
        <Kv label="Troféus" value="8.210" />
        <Kv label="Entrada" value="aprovação de administrador" />
        <Kv label="Permanência mínima" value="7 dias" />
      </Card>
      <Notice tone="orange" icon="info">
        Clã cheio não aceita solicitação até abrir vaga. Você pode entrar na lista de interesse.
      </Notice>
      <Btn tone="primary" toast="Interesse registrado no protótipo">
        Entrar na lista de interesse
      </Btn>
      <Btn tone="ghost" go="clan-discovery">
        Ver outros clãs
      </Btn>
    </Page>
  );
}

function ClanMembers() {
  const { palette } = useTheme();
  const { clan, clanMembers } = useApp();
  const members: ClanMember[] = clanMembers.length
    ? clanMembers
    : [
        { user_id: 'susan', display_name: 'Susan', role: 'leader', joined_at: '' },
        { user_id: 'rafa', display_name: 'Rafa', role: 'admin', joined_at: '' },
        { user_id: 'bia', display_name: 'Bia', role: 'admin', joined_at: '' },
        { user_id: 'jo', display_name: 'Jo', role: 'member', joined_at: '' },
        { user_id: 'nina', display_name: 'Nina', role: 'member', joined_at: '' },
        { user_id: 'caio', display_name: 'Caio', role: 'member', joined_at: '' },
      ];
  const roleLabel = (role: string) =>
    role === 'leader' ? 'Líder' : role === 'admin' ? 'Oficial' : 'Membro';
  return (
    <Page title="Membros">
      <Row between>
        <Txt variant="h3">{clan?.members ?? 24} membros</Txt>
        <Badge>3 oficiais</Badge>
      </Row>
      <CardList>
        {members.map((member, index) => (
          <ListRow key={member.user_id} last={index === members.length - 1}>
            <Avatar
              size={34}
              palette={palette}
              skin="#A6ABB1"
              hair="#17191B"
              shirt="#62686E"
              style={((index % 3) + 1) as 1 | 2 | 3}
            />
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                {member.display_name ?? 'Jogador'}
              </Text>
              <Text style={{ fontSize: 13, color: palette.muted }}>
                {roleLabel(member.role)} · online
              </Text>
            </View>
            <Badge
              tone={
                member.role === 'leader' ? 'lime' : member.role === 'admin' ? 'blue' : 'default'
              }
            >
              {roleLabel(member.role).toUpperCase()}
            </Badge>
          </ListRow>
        ))}
      </CardList>
      <BtnRow>
        <Btn tone="primary" go="clan-invite">
          Convidar
        </Btn>
        <Btn tone="ghost" toast="Cargos abertos no protótipo">
          Gerenciar cargos
        </Btn>
      </BtnRow>
    </Page>
  );
}

function ClanSettings() {
  const { palette } = useTheme();
  const nav = useNav();
  const { clan, session, setClan } = useApp();
  const [name, setName] = useState(clan?.name ?? 'Alpha Squad');
  const [description, setDescription] = useState(
    clan?.description ?? 'Grupo de futebol 5x5 e vôlei de terça e quinta.',
  );
  const leave = async () => {
    if (session && clan) {
      try {
        await api.clans.leave(session.accessToken, clan.id);
        setClan(null);
      } catch (error) {
        toastError(nav, error);
        return;
      }
    }
    nav.go('clan-discovery');
  };
  return (
    <Page title="Configurações do clã">
      <Field label="Nome">
        <Input value={name} onChangeText={setName} maxLength={40} />
      </Field>
      <Field label="Descrição">
        <Textarea value={description} onChangeText={setDescription} maxLength={280} />
      </Field>
      <Card>
        <Row between>
          <Txt variant="h3">Escudo</Txt>
          <Badge tone="green">LIVRE</Badge>
        </Row>
        <View style={{ flexDirection: 'row', gap: 8, marginTop: 10 }}>
          {['#E53935', '#62686E', '#62686E', '#E53935'].map((color, index) => (
            <View
              key={index}
              style={{
                width: 46,
                height: 46,
                borderRadius: 23,
                backgroundColor: color,
                borderWidth: index === 0 ? 2 : 1.5,
                borderColor: index === 0 ? '#17191B' : palette.line,
              }}
            />
          ))}
        </View>
      </Card>
      <Card>
        <Row between>
          <Txt variant="h3">Destaque no perfil</Txt>
          <Badge tone="blue">PASSE</Badge>
        </Row>
        <Txt variant="tiny" style={{ marginTop: 5 }}>
          Moldura, cor e posição em evidência. Não concede vantagem competitiva.
        </Txt>
      </Card>
      <BtnRow>
        <Btn tone="primary" toast="Configurações salvas no protótipo">
          Salvar
        </Btn>
        <Btn tone="ghost" onPress={leave}>
          Sair do clã
        </Btn>
      </BtnRow>
    </Page>
  );
}

function ClanChat() {
  const nav = useNav();
  const { palette } = useTheme();
  const { clan, clanMessages, session, loadClanMessages, loadClan } = useApp();
  const [extra, setExtra] = useState<typeof clanMessages>([]);
  const [input, setInput] = useState('');
  useEffect(() => {
    loadClan().catch(() => undefined);
  }, [loadClan]);
  const send = async () => {
    const body = input.trim();
    if (!body) {
      return;
    }
    if (session && clan) {
      try {
        await api.clans.sendMessage(session.accessToken, clan.id, body);
        await loadClanMessages(clan.id);
      } catch (error) {
        toastError(nav, error);
        return;
      }
    } else {
      setExtra((current) => [
        ...current,
        {
          id: String(Date.now()),
          sender_id: 'me',
          display_name: 'Você',
          body,
          hidden: false,
          created_at: new Date().toISOString(),
        },
      ]);
    }
    setInput('');
  };
  const combined = [...clanMessages, ...extra];
  const list = combined.length
    ? combined
    : [
        {
          id: '1',
          sender_id: 'rafa',
          display_name: 'Rafa',
          body: 'Terça 20h na Arena Sul. Quem fecha?',
          hidden: false,
          created_at: '',
        },
        {
          id: '2',
          sender_id: 'me',
          display_name: 'Você',
          body: 'Eu e a Bia. Falta 1.',
          hidden: false,
          created_at: '',
        },
        {
          id: '3',
          sender_id: 'jo',
          display_name: 'Jo',
          body: 'Vou.',
          hidden: false,
          created_at: '',
        },
      ];
  return (
    <Page title={clan?.name ?? 'Alpha Squad'}>
      <Card tone="flat" padding={9}>
        <Row between>
          <Txt variant="tiny">{clan?.members ?? 24} membros · chat permanente</Txt>
          <Badge tone="green">SÓ MEMBROS</Badge>
        </Row>
      </Card>
      <View style={{ gap: 10 }}>
        <SystemNotice>Rafa entrou no clã.</SystemNotice>
        {list.map((message) => {
          const mine = message.sender_id === 'me' || message.sender_id === session?.userId;
          return (
            <View
              key={message.id}
              style={{
                alignSelf: mine ? 'flex-end' : 'flex-start',
                maxWidth: '88%',
                paddingHorizontal: 12,
                paddingVertical: 10,
                borderRadius: 18,
                borderWidth: 1.5,
                borderColor: palette.line,
                backgroundColor: mine ? palette.limeSoft : palette.surface,
              }}
            >
              <Txt variant="tiny">
                <Text style={{ fontWeight: '800', color: palette.ink }}>
                  {mine ? 'Você' : (message.display_name ?? 'Membro')}
                </Text>
                {message.created_at ? ` · ${message.created_at.slice(11, 16)}` : ''}
              </Txt>
              <Text style={{ marginTop: 3, fontSize: 14, color: palette.ink }}>{message.body}</Text>
            </View>
          );
        })}
      </View>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <IconBtn icon="plus" label="Referência" modal="share" />
        <Input
          value={input}
          onChangeText={setInput}
          placeholder="Mensagem para o clã"
          maxLength={2000}
          style={{ flex: 1 }}
          onSubmitEditing={send}
        />
        <IconBtn icon="send" label="Enviar" ink onPress={send} />
      </View>
      <Row between>
        <Txt variant="tiny">Texto apenas · sem upload</Txt>
        <TextBtn go="report-message" muted>
          Denunciar
        </TextBtn>
      </Row>
    </Page>
  );
}

function ClanRanking() {
  const { palette } = useTheme();
  const { session, primaryFormatId } = useApp();
  const [entries, setEntries] = useState<
    { name: string; tag: string; trophies: number; position: number }[]
  >([]);
  useEffect(() => {
    if (session) {
      api.clans
        .ranking(session.accessToken, primaryFormatId ?? undefined)
        .then((result) => setEntries(result.entries))
        .catch(() => undefined);
    }
  }, [session, primaryFormatId]);
  const list = entries.length
    ? entries.map((item) => ({
        position: item.position,
        name: item.name,
        tag: item.tag,
        trophies: number(item.trophies),
        mine: item.name === 'Alpha Squad',
      }))
    : [
        { position: 1, name: 'Arena Norte FC', tag: '#ANFC', trophies: '14.820', mine: false },
        { position: 2, name: 'Quadra 9', tag: '#Q9', trophies: '13.440', mine: false },
        { position: 3, name: 'Clube Oeste', tag: '#CO', trophies: '12.910', mine: false },
        { position: 4, name: 'Alpha Squad', tag: '#ALPHA', trophies: '12.480', mine: true },
        { position: 5, name: 'Bairro Sul', tag: '#BS', trophies: '11.760', mine: false },
      ];
  return (
    <Page title="Ranking de clãs">
      <Seg>
        <SegBtn on>Futebol 5x5</SegBtn>
        <SegBtn>Vôlei 6x6</SegBtn>
      </Seg>
      <Row between>
        <Txt variant="tiny">Temporada 2026-Q4</Txt>
        <Badge>TOP 100</Badge>
      </Row>
      <CardList>
        {list.map((item, index) => (
          <ListRow key={`${item.position}-${item.name}`} last={index === list.length - 1}>
            <Text
              style={{
                width: 28,
                fontWeight: '900',
                fontVariant: ['tabular-nums'],
                color: palette.ink,
              }}
            >
              #{item.position}
            </Text>
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                {item.name}
              </Text>
              <Text style={{ fontSize: 13, color: palette.muted }}>
                {item.mine ? 'seu clã' : 'clã verificado'}
              </Text>
            </View>
            <Txt variant="num" style={{ fontSize: 16 }}>
              {item.trophies}
            </Txt>
          </ListRow>
        ))}
      </CardList>
    </Page>
  );
}

function Ranking() {
  const { palette } = useTheme();
  const { session, primaryFormatId, ratings } = useApp();
  const [entries, setEntries] = useState<
    { position: number; name: string; division: string; matches: number }[]
  >([]);
  const [position, setPosition] = useState<number | null>(null);
  const [sport, setSport] = useState('Futebol 5x5');
  useEffect(() => {
    if (session && primaryFormatId) {
      api.ratings
        .ranking(session.accessToken, primaryFormatId)
        .then((result) => {
          setEntries(
            result.entries.map((item) => ({
              position: item.position,
              name: item.display_name ?? 'Jogador',
              division: divisionLabel(item.division),
              matches: item.matches_played,
            })),
          );
          setPosition(ratings[primaryFormatId]?.position ?? null);
        })
        .catch(() => undefined);
    }
  }, [session, primaryFormatId, ratings]);
  const list = entries.slice(0, 5);
  const myRating = primaryFormatId ? ratings[primaryFormatId] : undefined;
  return (
    <Page title="Ranking">
      <Seg>
        {['Futebol 5x5', 'Vôlei 6x6'].map((item) => (
          <SegBtn key={item} on={sport === item} onPress={() => setSport(item)}>
            {item}
          </SegBtn>
        ))}
      </Seg>
      <Card tone="blue">
        <Row between>
          <Badge tone="blue">SUA POSIÇÃO</Badge>
          <Badge>{position ? `#${position}` : '—'}</Badge>
        </Row>
        <Txt variant="h2" style={{ marginTop: 8 }}>
          {myRating?.provisional ? 'Provisório' : myRating ? divisionLabel(myRating.division) : '—'}{' '}
          · {myRating?.matches_played ?? 0} partidas
        </Txt>
        <Txt variant="tiny">Top 100 por formato · posição individual</Txt>
      </Card>
      {list.length ? (
        <CardList>
          {list.map((item, index) => (
            <ListRow key={item.position} last={index === list.length - 1}>
              <Text style={{ width: 28, fontWeight: '900', color: palette.ink }}>
                #{item.position}
              </Text>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                  {item.name}
                </Text>
                <Text style={{ fontSize: 13, color: palette.muted }}>{item.division}</Text>
              </View>
              <Txt variant="tiny">{item.matches} partidas</Txt>
            </ListRow>
          ))}
        </CardList>
      ) : (
        <EmptyState
          title="Ranking vazio"
          text="Jogadores aparecem aqui depois das primeiras partidas ranqueadas."
        />
      )}
      <Notice tone="blue" icon="info">
        As 5 primeiras partidas ranqueadas aparecem como “Provisório”.
      </Notice>
    </Page>
  );
}

function Notifications() {
  const { palette } = useTheme();
  const nav = useNav();
  const {
    notifications,
    unreadNotifications,
    loadNotifications,
    markNotificationRead,
    markAllNotificationsRead,
  } = useApp();
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    loadNotifications()
      .catch(() => {
        if (active) {
          setFailed(true);
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [loadNotifications]);

  const retry = () => {
    setLoading(true);
    setFailed(false);
    loadNotifications()
      .catch(() => setFailed(true))
      .finally(() => setLoading(false));
  };

  const open = (item: Notification) => {
    if (!item.read_at) {
      markNotificationRead(item.id).catch(() => undefined);
    }
    const data = item.data ?? {};
    const matchId = typeof data.match_id === 'string' ? data.match_id : undefined;
    if (item.kind.includes('booking')) {
      nav.go('booking-history');
      return;
    }
    if (item.kind.startsWith('moderation')) {
      nav.go('moderation-status');
      return;
    }
    if (item.kind.includes('result')) {
      nav.go('result-review', matchId ? { matchId } : undefined);
      return;
    }
    if (item.kind.includes('match') || item.kind.includes('lobby')) {
      nav.go('lobby-detail', matchId ? { matchId } : undefined);
      return;
    }
    if (item.kind.includes('invite')) {
      nav.go('lobby-invite-received');
      return;
    }
    if (item.kind.includes('clan')) {
      nav.go('clan');
    }
  };

  if (loading) {
    return (
      <Page title="Notificações">
        <LoadingState label="Buscando notificações." variant="list" />
      </Page>
    );
  }

  if (failed) {
    return (
      <Page title="Notificações">
        <StateScreen
          icon="wifi-off"
          title="Não foi possível carregar as notificações"
          text="Verifique a conexão e tente novamente. O histórico continua salvo no servidor."
          actions={
            <Btn tone="primary" onPress={retry}>
              Tentar novamente
            </Btn>
          }
        />
      </Page>
    );
  }

  if (!notifications.length) {
    return (
      <Page title="Notificações">
        <EmptyState
          title="Nenhuma notificação"
          text="Prazos, reservas, convites e resultados aparecem aqui."
        />
      </Page>
    );
  }

  return (
    <Page
      title="Notificações"
      sub={unreadNotifications > 0 ? `${unreadNotifications} não lidas` : 'Tudo em dia'}
    >
      <Row between>
        <Txt variant="tiny">Recentes</Txt>
        {unreadNotifications > 0 ? (
          <TextBtn onPress={() => markAllNotificationsRead().catch(() => undefined)}>
            Marcar lidas
          </TextBtn>
        ) : (
          <Txt variant="tiny">Sem pendências</Txt>
        )}
      </Row>
      <CardList>
        {notifications.map((item, index) => {
          const unread = !item.read_at;
          const decision =
            item.kind === 'moderation_appeal_result' && typeof item.data?.decision === 'string'
              ? item.data.decision
              : null;
          const decisionLabel = appealDecisionLabel(decision);
          return (
            <ListRow
              key={item.id}
              last={index === notifications.length - 1}
              onPress={() => open(item)}
            >
              <View
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: 4,
                  backgroundColor: unread ? palette.lime : palette.lineStrong,
                }}
              />
              <View style={{ flex: 1 }}>
                <Row between>
                  <Text
                    numberOfLines={2}
                    style={{ flex: 1, fontSize: 14, fontWeight: '800', color: palette.ink }}
                  >
                    {item.title}
                  </Text>
                  <Txt variant="tiny">{shortDateTime(item.created_at)}</Txt>
                </Row>
                <Text
                  numberOfLines={3}
                  style={{ fontSize: 13, color: palette.muted, marginTop: 2 }}
                >
                  {item.body}
                </Text>
                {decisionLabel ? (
                  <View style={{ marginTop: 6 }}>
                    <Badge tone={decision === 'ACCEPTED' ? 'green' : 'red'}>{decisionLabel}</Badge>
                  </View>
                ) : null}
              </View>
              {unread ? <Badge tone="lime">NOVA</Badge> : null}
            </ListRow>
          );
        })}
      </CardList>
    </Page>
  );
}

let moderationDraftMessageIds: string[] = [];

const REPORT_CATEGORIES: { code: string; label: string; sub: string }[] = [
  { code: 'HARASSMENT', label: 'Assédio', sub: 'Ofensas, perseguição ou hostilidade' },
  { code: 'HATE', label: 'Discurso de ódio', sub: 'Ataque a grupo ou pessoa' },
  { code: 'THREAT', label: 'Ameaça', sub: 'Risco à segurança' },
  { code: 'SEXUAL', label: 'Conteúdo sexual', sub: 'Sem consentimento ou impróprio' },
  { code: 'SPAM', label: 'Spam', sub: 'Divulgação repetida ou golpe' },
  { code: 'OTHER', label: 'Outro', sub: 'Outra violação das regras' },
];

function reportCategoryLabel(code: string): string {
  return REPORT_CATEGORIES.find((item) => item.code === code)?.label ?? 'Outro';
}

function moderationStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    OPEN: 'Em análise',
    RECEIVED: 'Recebida',
    TRIAGE: 'Em triagem',
    UNDER_REVIEW: 'Em análise',
    RESOLVED: 'Decidida',
    CLOSED: 'Encerrada',
    DECIDED: 'Decidida',
    REJECTED: 'Não procede',
    ACTIVE: 'Ativa',
    REVOKED: 'Revogada',
    EXPIRED: 'Expirada',
    PENDING: 'Pendente',
    APPROVED: 'Aprovado',
  };
  return labels[status] ?? status.replaceAll('_', ' ');
}

function moderationActionLabel(actionType: string): string {
  const labels: Record<string, string> = {
    WARNING: 'Advertência',
    RESTRICT_RANKED: 'Restrição da fila ranqueada',
    SUSPEND_TEMP: 'Suspensão temporária',
    RESTRICTION: 'Restrição temporária',
    SUSPENSION: 'Suspensão',
    BAN: 'Banimento',
    MUTE: 'Silenciamento',
  };
  return labels[actionType] ?? actionType.replaceAll('_', ' ');
}

function appealDecisionLabel(decision: string | null): string | null {
  if (decision === 'ACCEPTED') {
    return 'RECURSO ACEITO';
  }
  if (decision === 'REJECTED') {
    return 'RECURSO REJEITADO';
  }
  return null;
}

function ReportProfile() {
  const nav = useNav();
  const { session, matches, queue } = useApp();
  const targetUserId = typeof nav.params.userId === 'string' ? nav.params.userId : null;
  const targetName = typeof nav.params.name === 'string' ? nav.params.name : 'Jogador';
  const lobbyId =
    (typeof nav.params.lobbyId === 'string' && nav.params.lobbyId) ||
    matches.find((match) => match.lobby_id)?.lobby_id ||
    queue?.lobby?.id ||
    null;
  const [category, setCategory] = useState('HARASSMENT');
  const [description, setDescription] = useState('');
  const [busy, setBusy] = useState(false);
  const attached = moderationDraftMessageIds;
  const canSubmit = !!session && !!targetUserId && !!lobbyId && description.trim().length > 0;

  const submit = async () => {
    if (!session || !targetUserId || !lobbyId) {
      return;
    }
    if (!description.trim()) {
      nav.toast('Descreva o que aconteceu para enviar a denúncia.');
      return;
    }
    setBusy(true);
    try {
      const report = await api.moderation.createReport(session.accessToken, {
        target_user_id: targetUserId,
        lobby_id: lobbyId,
        category,
        description: description.trim(),
        message_ids: attached,
      });
      moderationDraftMessageIds = [];
      nav.replace('moderation-status', { reportId: report.id });
      nav.toast('Denúncia enviada. A triagem é interna.');
    } catch (error) {
      const messages: Record<string, string> = {
        forbidden: 'Você não pode denunciar este jogador neste lobby.',
        invalid_target: 'Jogador inválido.',
        report_exists: 'Já existe uma denúncia sua para este caso.',
        invalid_messages: 'As mensagens anexadas não pertencem a este lobby.',
        rate_limited: 'Muitas denúncias em pouco tempo. Aguarde.',
      };
      nav.toast(
        error instanceof ApiError
          ? (messages[error.code] ?? 'Não foi possível enviar a denúncia.')
          : 'Não foi possível enviar a denúncia.',
      );
    } finally {
      setBusy(false);
    }
  };

  if (!targetUserId) {
    return (
      <Page title="Denunciar jogador">
        <StateScreen
          icon="shield"
          title="Escolha o jogador"
          text="Abra o perfil do jogador que você quer denunciar. A denúncia precisa de um alvo e de um lobby em comum."
          actions={
            <Btn tone="primary" go="friends">
              Ver amigos
            </Btn>
          }
        />
      </Page>
    );
  }

  if (!lobbyId) {
    return (
      <Page title="Denunciar jogador">
        <StateScreen
          icon="users"
          title="Escolha um lobby"
          text="O contexto da denúncia vem de um lobby em comum. Entre em uma partida e abra a denúncia pelo perfil do jogador."
          actions={
            <>
              <Btn tone="primary" go="matches">
                Ver partidas
              </Btn>
              <Btn tone="ghost" go="queue-casual">
                Buscar partida
              </Btn>
            </>
          }
        />
      </Page>
    );
  }

  return (
    <Page title="Denunciar jogador">
      <Txt variant="lead">{targetName} · contexto do lobby</Txt>
      <Card>
        <Txt variant="h3">Categoria</Txt>
        <ChipRow style={{ marginTop: 8 }}>
          {REPORT_CATEGORIES.map((item) => (
            <Chip
              key={item.code}
              on={category === item.code}
              onPress={() => setCategory(item.code)}
            >
              {item.label}
            </Chip>
          ))}
        </ChipRow>
        <Txt variant="tiny" style={{ marginTop: 8 }}>
          {REPORT_CATEGORIES.find((item) => item.code === category)?.sub}
        </Txt>
      </Card>
      <Btn
        tone="ghost"
        icon="chat"
        onPress={() =>
          nav.go('report-message', {
            userId: targetUserId,
            name: targetName,
            lobbyId,
          })
        }
      >
        Selecionar mensagens
      </Btn>
      {attached.length ? (
        <Notice tone="blue" icon="chat">
          {attached.length} mensagem(ns) anexada(s) como contexto.
        </Notice>
      ) : (
        <Notice tone="blue" icon="info">
          Você pode anexar até 5 mensagens do lobby. Sem fotos ou mídia.
        </Notice>
      )}
      <Field label="Contexto (obrigatório)">
        <Textarea
          value={description}
          onChangeText={setDescription}
          maxLength={2000}
          placeholder="Explique o que aconteceu. Até 2.000 caracteres."
        />
      </Field>
      <Row between>
        <Txt variant="tiny">Mínimo 1 caractere</Txt>
        <Txt variant="tiny">{description.length} / 2.000</Txt>
      </Row>
      <Notice tone="blue" icon="shield">
        A denúncia é privada. O alvo não vê quem denunciou. Não há punição automática; a triagem é
        interna e não expõe prioridade ou severidade.
      </Notice>
      <Btn tone="primary" onPress={submit} disabled={!canSubmit || busy}>
        {busy ? 'Enviando…' : 'Enviar denúncia'}
      </Btn>
    </Page>
  );
}

function ReportMessage() {
  const { palette } = useTheme();
  const nav = useNav();
  const { session, matches } = useApp();
  const lobbyId =
    (typeof nav.params.lobbyId === 'string' && nav.params.lobbyId) ||
    matches.find((match) => match.lobby_id)?.lobby_id ||
    null;
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [selected, setSelected] = useState<string[]>(moderationDraftMessageIds);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!session || !lobbyId) {
      return;
    }
    let active = true;
    api.chat
      .list(session.accessToken, lobbyId)
      .then((result) => {
        if (active) {
          setMessages(result.messages.slice(-20));
        }
      })
      .catch(() => {
        if (active) {
          setFailed(true);
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [session, lobbyId]);

  const toggle = (messageId: string) => {
    if (selected.includes(messageId)) {
      setSelected((current) => current.filter((value) => value !== messageId));
      return;
    }
    if (selected.length >= 5) {
      nav.toast('Selecione no máximo 5 mensagens.');
      return;
    }
    setSelected((current) => [...current, messageId]);
  };

  const attach = () => {
    moderationDraftMessageIds = selected;
    nav.back();
  };

  if (!session) {
    return (
      <Page title="Selecionar mensagens">
        <StateScreen
          icon="lock"
          title="Entre na sua conta"
          text="As mensagens do lobby são privadas e só podem ser anexadas por participantes autenticados."
          actions={
            <Btn tone="primary" back>
              Voltar
            </Btn>
          }
        />
      </Page>
    );
  }

  if (!lobbyId) {
    return (
      <Page title="Selecionar mensagens">
        <StateScreen
          icon="chat"
          title="Lobby não informado"
          text="Abra a denúncia pelo perfil do jogador dentro de um lobby em comum."
          actions={
            <Btn tone="primary" back>
              Voltar
            </Btn>
          }
        />
      </Page>
    );
  }

  if (loading) {
    return (
      <Page title="Selecionar mensagens">
        <LoadingState label="Buscando mensagens do lobby." variant="list" />
      </Page>
    );
  }

  if (failed) {
    return (
      <Page title="Selecionar mensagens">
        <StateScreen
          icon="wifi-off"
          title="Não foi possível carregar as mensagens"
          text="Verifique a conexão e tente novamente."
          actions={
            <Btn tone="primary" back>
              Voltar
            </Btn>
          }
        />
      </Page>
    );
  }

  if (!messages.length) {
    return (
      <Page title="Selecionar mensagens">
        <EmptyState
          title="Nenhuma mensagem no lobby"
          text="Você ainda pode descrever o ocorrido no campo de contexto da denúncia."
          actions={
            <Btn tone="primary" back>
              Voltar à denúncia
            </Btn>
          }
        />
      </Page>
    );
  }

  return (
    <Page title="Selecionar mensagens">
      <Txt variant="lead">
        Escolha até 5 mensagens. A triagem é interna e usa apenas o contexto selecionado; não há
        upload de mídia.
      </Txt>
      <CardList>
        {messages.map((message, index) => {
          const checked = selected.includes(message.id);
          const mine = message.sender_id === session?.userId;
          return (
            <ListRow
              key={message.id}
              last={index === messages.length - 1}
              onPress={() => toggle(message.id)}
            >
              <View
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
                {checked ? (
                  <Text style={{ color: palette.onInk, fontSize: 12, fontWeight: '900' }}>✓</Text>
                ) : null}
              </View>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                  {mine ? 'Você' : 'Jogador'}
                </Text>
                <Text style={{ fontSize: 13, color: palette.muted, marginTop: 2 }}>
                  {shortDateTime(message.created_at)} · {message.body}
                </Text>
              </View>
            </ListRow>
          );
        })}
      </CardList>
      <Row between>
        <Txt variant="tiny">{selected.length} de 5 selecionadas</Txt>
        <Badge tone="blue">CONTEXTO DO LOBBY</Badge>
      </Row>
      <Btn tone="primary" onPress={attach} disabled={selected.length === 0}>
        Anexar à denúncia
      </Btn>
    </Page>
  );
}

function ModerationStatus() {
  const nav = useNav();
  const { palette } = useTheme();
  const { session } = useApp();
  const [reports, setReports] = useState<ModerationReport[]>([]);
  const [actions, setActions] = useState<ModerationAction[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [appealActionId, setAppealActionId] = useState<string | null>(null);
  const [appealText, setAppealText] = useState('');
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    if (!session) {
      return;
    }
    const [reportResult, actionResult] = await Promise.all([
      api.moderation.listMyReports(session.accessToken),
      api.moderation.listMyActions(session.accessToken),
    ]);
    setReports(reportResult.reports);
    setActions(actionResult.actions);
  }, [session]);

  useEffect(() => {
    let active = true;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh()
      .catch(() => {
        if (active) {
          setFailed(true);
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [refresh]);

  const retry = () => {
    setLoading(true);
    setFailed(false);
    refresh()
      .catch(() => setFailed(true))
      .finally(() => setLoading(false));
  };

  const submitAppeal = async () => {
    if (!session || !appealActionId) {
      return;
    }
    if (!appealText.trim()) {
      nav.toast('Explique o motivo do recurso.');
      return;
    }
    setBusy(true);
    try {
      await api.moderation.appeal(session.accessToken, appealActionId, appealText.trim());
      nav.toast('Recurso enviado.');
      setAppealActionId(null);
      setAppealText('');
      await refresh();
    } catch (error) {
      const messages: Record<string, string> = {
        not_found: 'Medida não encontrada.',
        appeal_exists: 'Você já enviou um recurso para esta medida.',
        appeal_window_closed: 'O prazo para recorrer desta medida terminou.',
        forbidden: 'Você não pode recorrer desta medida.',
      };
      nav.toast(
        error instanceof ApiError
          ? (messages[error.code] ?? 'Não foi possível enviar o recurso.')
          : 'Não foi possível enviar o recurso.',
      );
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <Page title="Moderação">
        <LoadingState label="Buscando suas denúncias e medidas." variant="list" />
      </Page>
    );
  }

  if (failed) {
    return (
      <Page title="Moderação">
        <StateScreen
          icon="wifi-off"
          title="Não foi possível carregar a moderação"
          text="Verifique a conexão e tente novamente. O histórico continua salvo no servidor."
          actions={
            <Btn tone="primary" onPress={retry}>
              Tentar novamente
            </Btn>
          }
        />
      </Page>
    );
  }

  if (!reports.length && !actions.length) {
    return (
      <Page title="Moderação">
        <EmptyState
          title="Nenhuma denúncia ou medida"
          text="Quando você denunciar um jogador ou receber uma medida, o status aparece aqui. A triagem interna não é exposta."
        />
      </Page>
    );
  }

  const appealAction = actions.find((item) => item.id === appealActionId) ?? null;

  return (
    <Page title="Moderação">
      <Txt variant="lead">
        Acompanhe apenas status, categoria, data e decisão. Prioridade, severidade e quem denunciou
        não são expostos.
      </Txt>
      {actions.length ? (
        <>
          <Row between>
            <Txt variant="h3">Medidas</Txt>
            <Badge tone="blue">{actions.length}</Badge>
          </Row>
          <CardList>
            {actions.map((action, index) => {
              const canAppeal =
                action.status !== 'REVOKED' && action.status !== 'EXPIRED' && !action.revoked_at;
              return (
                <ListRow key={action.id} last={index === actions.length - 1}>
                  <View style={{ flex: 1 }}>
                    <Row between>
                      <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                        {moderationActionLabel(action.action_type)}
                      </Text>
                      <Badge tone={action.status === 'ACTIVE' ? 'orange' : 'default'}>
                        {moderationStatusLabel(action.status)}
                      </Badge>
                    </Row>
                    <Text style={{ fontSize: 13, color: palette.muted, marginTop: 2 }}>
                      {shortDateTime(action.starts_at)}
                      {action.ends_at ? ` · até ${shortDateTime(action.ends_at)}` : ''}
                    </Text>
                    {action.reason ? (
                      <Text style={{ fontSize: 13, color: palette.muted, marginTop: 2 }}>
                        Decisão: {action.reason}
                      </Text>
                    ) : null}
                    {canAppeal ? (
                      <View style={{ marginTop: 4 }}>
                        <TextBtn onPress={() => setAppealActionId(action.id)}>Recorrer</TextBtn>
                      </View>
                    ) : null}
                  </View>
                </ListRow>
              );
            })}
          </CardList>
        </>
      ) : null}

      {appealAction ? (
        <Card>
          <Txt variant="h3">Recurso · {moderationActionLabel(appealAction.action_type)}</Txt>
          <Txt variant="tiny" style={{ marginTop: 4, marginBottom: 10 }}>
            Explique por que a medida deve ser revista. Até 1.000 caracteres.
          </Txt>
          <Textarea
            value={appealText}
            onChangeText={setAppealText}
            maxLength={1000}
            placeholder="Motivo do recurso"
          />
          <View style={{ marginTop: 10 }}>
            <BtnRow>
              <Btn tone="ghost" onPress={() => setAppealActionId(null)}>
                Cancelar
              </Btn>
              <Btn tone="primary" onPress={submitAppeal} disabled={busy}>
                {busy ? 'Enviando…' : 'Enviar recurso'}
              </Btn>
            </BtnRow>
          </View>
        </Card>
      ) : null}

      {reports.length ? (
        <>
          <Row between>
            <Txt variant="h3">Denúncias</Txt>
            <Badge tone="blue">{reports.length}</Badge>
          </Row>
          <CardList>
            {reports.map((report, index) => (
              <ListRow key={report.id} last={index === reports.length - 1}>
                <View style={{ flex: 1 }}>
                  <Row between>
                    <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                      {reportCategoryLabel(report.category)}
                    </Text>
                    <Badge tone={report.status === 'RESOLVED' ? 'green' : 'orange'}>
                      {moderationStatusLabel(report.status)}
                    </Badge>
                  </Row>
                  <Text style={{ fontSize: 13, color: palette.muted, marginTop: 2 }}>
                    {shortDateTime(report.created_at)}
                    {report.reviewed_at
                      ? ` · revisada em ${shortDateTime(report.reviewed_at)}`
                      : ''}
                  </Text>
                  {report.decision_reason ? (
                    <Text style={{ fontSize: 13, color: palette.muted, marginTop: 2 }}>
                      Decisão: {report.decision_reason}
                    </Text>
                  ) : (
                    <Text style={{ fontSize: 13, color: palette.muted, marginTop: 2 }}>
                      Sem decisão publicada.
                    </Text>
                  )}
                </View>
              </ListRow>
            ))}
          </CardList>
        </>
      ) : null}
      <Notice tone="blue" icon="shield">
        A triagem é interna. Uma denúncia isolada não gera punição automática.
      </Notice>
    </Page>
  );
}

function BlockUser() {
  const { palette } = useTheme();
  return (
    <Page title="Bloquear">
      <Card>
        <Row>
          <Avatar
            size={86}
            skin="#62686E"
            hair="#17191B"
            shirt="#62686E"
            style={2}
            glasses
            palette={palette}
          />
          <View style={{ flex: 1 }}>
            <Txt variant="h3">Marcus_rise</Txt>
            <Txt variant="tiny">#9034 · Alpha Squad</Txt>
          </View>
        </Row>
      </Card>
      <Card>
        <Kv label="Amizade" value="removida" />
        <Kv label="Convites" value="bloqueados" />
        <Kv label="Mensagens" value="bloqueadas" />
        <Kv label="Notificação ao outro" value="não" />
      </Card>
      <Btn tone="danger" modal="block">
        Bloquear usuário
      </Btn>
      <Btn tone="ghost" back>
        Cancelar
      </Btn>
    </Page>
  );
}

function ClanInvite() {
  const { palette } = useTheme();
  const [selected, setSelected] = useState<string[]>(['rafa', 'bia']);
  const list = [
    { id: 'rafa', name: 'Rafa', tag: '#2210', meta: 'Amizade aceita' },
    { id: 'bia', name: 'Bia', tag: '#7781', meta: 'Amizade aceita' },
    { id: 'jo', name: 'Jo', tag: '#1904', meta: 'Solicitação pendente' },
  ];
  return (
    <Page title="Convidar membros">
      <Input placeholder="Buscar amigo por nome#tag" maxLength={60} />
      <CardList>
        {list.map((friend, index) => {
          const checked = selected.includes(friend.id);
          return (
            <ListRow key={friend.id} last={index === list.length - 1}>
              <Avatar
                size={34}
                palette={palette}
                skin="#A6ABB1"
                hair="#17191B"
                shirt="#62686E"
                style={((index % 3) + 1) as 1 | 2 | 3}
              />
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                  {friend.name}{' '}
                  <Text style={{ color: palette.muted, fontWeight: '400' }}>{friend.tag}</Text>
                </Text>
                <Text style={{ fontSize: 13, color: palette.muted }}>{friend.meta}</Text>
              </View>
              <View
                onTouchEnd={() => {
                  if (friend.id === 'jo') {
                    return;
                  }
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
                  borderColor: checked ? palette.ink : palette.line,
                  backgroundColor: checked ? palette.ink : palette.surface,
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                {checked ? <Text style={{ color: palette.onInk, fontSize: 12 }}>✓</Text> : null}
              </View>
            </ListRow>
          );
        })}
      </CardList>
      <Notice tone="blue" icon="info">
        Clã cheio não aceita convite. O convite expira e não garante vaga.
      </Notice>
      <Btn tone="primary" toast="Convites de clã enviados no protótipo">
        Enviar convites
      </Btn>
    </Page>
  );
}

function ClanFull() {
  return (
    <Page title="Arena Norte FC">
      <StateScreen
        icon="users"
        title="Clã cheio"
        text="30 de 30 membros. Você pode entrar na lista de interesse; se abrir vaga, o convite respeita a ordem e a permanência mínima."
        actions={
          <>
            <Btn tone="primary" toast="Interesse registrado no protótipo">
              Entrar na lista
            </Btn>
            <Btn tone="ghost" go="clan-discovery">
              Ver outros clãs
            </Btn>
          </>
        }
      />
    </Page>
  );
}

export const socialScreens: ScreenDef[] = [
  { id: 'friends', tab: 'social', render: () => <Friends /> },
  { id: 'add-friend', tab: 'social', render: () => <AddFriend /> },
  { id: 'clan', tab: 'social', render: () => <ClanProfile /> },
  { id: 'clan-discovery', tab: 'social', render: () => <ClanDiscovery /> },
  { id: 'clan-create', tab: 'social', render: () => <ClanCreate /> },
  { id: 'clan-join', tab: 'social', render: () => <ClanJoin /> },
  { id: 'clan-members', tab: 'social', render: () => <ClanMembers /> },
  { id: 'clan-settings', tab: 'social', render: () => <ClanSettings /> },
  { id: 'clan-chat', tab: 'social', render: () => <ClanChat /> },
  { id: 'clan-ranking', tab: 'social', render: () => <ClanRanking /> },
  { id: 'ranking', tab: 'social', render: () => <Ranking /> },
  { id: 'notifications', tab: 'social', render: () => <Notifications /> },
  { id: 'report-profile', tab: 'social', render: () => <ReportProfile /> },
  { id: 'report-message', tab: 'social', render: () => <ReportMessage /> },
  { id: 'moderation-status', tab: 'social', render: () => <ModerationStatus /> },
  { id: 'block-user', tab: 'social', render: () => <BlockUser /> },
  { id: 'clan-invite', tab: 'social', render: () => <ClanInvite /> },
  { id: 'clan-full', tab: 'social', render: () => <ClanFull /> },
];
