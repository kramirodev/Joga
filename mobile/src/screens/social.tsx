import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AccessibilityInfo,
  BackHandler,
  FlatList,
  Pressable,
  RefreshControl,
  View,
} from 'react-native';

import { api, ApiError } from '../api/client';
import type {
  ChatMessage,
  Clan,
  ClanInvite as ClanInviteData,
  ClanMember,
  ClanRanking as ClanRankingData,
  ModerationAction,
  ModerationReport,
  MyRating,
  Notification,
  SportFormat,
} from '../api/types';
import { useApp } from '../state/app';
import {
  clanUpdatePatch,
  displayClanTag,
  inviteExpiryLabel,
  isAdminRole,
  isDuplicateReport,
  isOwnerRole,
  isReportableMessage,
  joinPolicyExplanation,
  joinPolicyLabel,
  matchesSearch,
  memberDisplayName,
  mergeChatRows,
  myRoleLabel,
  normalizeTagInput,
  sortMembers,
  tagIsValid,
  tagPayload,
  type ChatRow,
} from '../state/clanSocial';
import { lobbyIdFromQueue } from '../state/queueState';
import { BottomSheetFrame, useSheetClose } from '../ui/BottomSheetFrame';
import { useNav, useTheme } from '../state/context';
import { IdentityBadge } from '../ui/IdentityBadge';
import { identityFromSeed } from '../ui/identity';
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
  InputPrefix,
  Kv,
  ListRow,
  LoadingState,
  Notice,
  Page,
  Row,
  Seg,
  SegBtn,
  SegContent,
  StateScreen,
  Textarea,
  TextBtn,
  Txt,
} from '../ui/kit';
import { divisionLabel, number, shortDateTime } from '../ui/datetime';
import { Text } from '../ui/text';
import type { ScreenDef } from './types';

function apiErrorCode(error: unknown): string {
  return error instanceof ApiError ? error.code : '';
}

type FormatOption = SportFormat;

/**
 * Formatos do catálogo global — mesma fonte do passo 1 da busca. Nunca uma
 * lista fixa de esportes. Se o catálogo falhar, a tela oferece tentar de novo
 * em vez de inventar opções.
 */
function useFormatOptions() {
  const { catalog, loadCatalog } = useApp();
  const formats = useMemo<FormatOption[]>(
    () => catalog.flatMap((sport) => sport.formats),
    [catalog],
  );
  const [busy, setBusy] = useState(catalog.length === 0);
  const [failed, setFailed] = useState(false);
  const retry = useCallback(async () => {
    setBusy(true);
    setFailed(false);
    try {
      await loadCatalog();
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  }, [loadCatalog]);
  useEffect(() => {
    if (catalog.length > 0) {
      return;
    }
    let active = true;
    loadCatalog()
      .then(() => {
        if (active) {
          setBusy(false);
          setFailed(false);
        }
      })
      .catch(() => {
        if (active) {
          setBusy(false);
          setFailed(true);
        }
      });
    return () => {
      active = false;
    };
  }, [catalog.length, loadCatalog]);
  return { formats, busy, failed, retry };
}

function FormatPicker({
  formats,
  busy,
  failed,
  retry,
  value,
  onChange,
}: {
  formats: FormatOption[];
  busy: boolean;
  failed: boolean;
  retry: () => void;
  value: string | null;
  onChange: (formatId: string) => void;
}) {
  if (busy) {
    return <LoadingState label="Carregando esportes." variant="generic" />;
  }
  if (failed || formats.length === 0) {
    return (
      <View style={{ gap: 8 }}>
        <Txt variant="tiny">
          {failed ? 'Não foi possível carregar os esportes.' : 'Nenhum esporte disponível.'}
        </Txt>
        <TextBtn onPress={retry}>Tentar novamente</TextBtn>
      </View>
    );
  }
  return (
    <ChipRow>
      {formats.map((format) => {
        const selected = format.id === value;
        return (
          <Chip
            key={format.id}
            on={selected}
            onPress={() => onChange(format.id)}
            accessibilityLabel={`${format.name}, ${selected ? 'selecionado' : 'não selecionado'}`}
          >
            {format.name}
          </Chip>
        );
      })}
    </ChipRow>
  );
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
          <SegContent value={tab}>
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
                      <IdentityBadge
                        size={34}
                        identity={identityFromSeed(friend.id)}
                        palette={palette}
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
          </SegContent>
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
  const [failed, setFailed] = useState(false);
  const [retryTick, setRetryTick] = useState(0);
  useEffect(() => {
    let active = true;
    loadClan()
      .then(() => {
        if (active) {
          setFailed(false);
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
  }, [loadClan, retryTick]);
  if (loading && !clan) {
    return (
      <Page title="Clã">
        <LoadingState label="Buscando seu clã." variant="clan" />
      </Page>
    );
  }
  if (failed && !clan) {
    return (
      <Page title="Clã">
        <StateScreen
          icon="wifi-off"
          title="Não foi possível carregar seu clã"
          text="Verifique a conexão e tente novamente."
          actions={
            <Btn
              tone="primary"
              onPress={() => {
                setLoading(true);
                setRetryTick((value) => value + 1);
              }}
            >
              Tentar novamente
            </Btn>
          }
        />
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
      {failed ? (
        <View style={{ gap: 6 }}>
          <Notice tone="orange" icon="alert">
            Não foi possível atualizar o clã. Os dados abaixo podem estar desatualizados.
          </Notice>
          <TextBtn onPress={() => setRetryTick((value) => value + 1)}>Tentar novamente</TextBtn>
        </View>
      ) : null}
      <Card tone="ink">
        <Row between>
          <Badge tone={clan.join_policy === 'open' ? 'lime' : 'default'}>
            {joinPolicyLabel(clan.join_policy)}
          </Badge>
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
              {displayClanTag(clan.tag)} · {clan.members} de {clan.max_members} membros
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
            sub: `${clanMembers.length} ${clanMembers.length === 1 ? 'membro' : 'membros'}`,
            go: 'clan-members',
          },
          {
            icon: 'gear' as const,
            title: 'Configurações do clã',
            sub: 'Editar nome, descrição e entrada',
            go: 'clan-settings',
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
        O escudo aparece no perfil do clã. O destaque extra é do passe.
      </Notice>
    </Page>
  );
}

function joinErrorMessage(code: string): string {
  const map: Record<string, string> = {
    already_member: 'Você já é membro deste clã.',
    already_in_clan: 'Você já está em outro clã. Saia do atual antes de entrar em outro.',
    clan_full: 'Clã cheio. Volte quando abrir uma vaga.',
    clan_cooldown: 'Você saiu de um clã há menos de 7 dias. Tente novamente mais tarde.',
    clan_closed: 'Este clã não aceita novas entradas.',
    not_found: 'Clã não encontrado. Atualize a lista.',
    network_unavailable: 'Sem conexão. Tente novamente.',
    request_timeout: 'A conexão demorou demais. Tente novamente.',
  };
  return map[code] ?? 'Não foi possível entrar no clã. Tente novamente.';
}

type ClanOpenFilter = 'all' | 'open' | 'closed';

function ClanDiscovery() {
  const nav = useNav();
  const { session, clan: myClan, loadClan } = useApp();
  const token = session?.accessToken ?? null;
  const [query, setQuery] = useState('');
  const [appliedQuery, setAppliedQuery] = useState('');
  const [openFilter, setOpenFilter] = useState<ClanOpenFilter>('all');
  const [withSlots, setWithSlots] = useState(false);
  const [result, setResult] = useState<{
    key: string;
    status: 'ready' | 'error';
    clans: Clan[];
  } | null>(null);
  const [joinError, setJoinError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [retryTick, setRetryTick] = useState(0);
  const requestSeq = useRef(0);
  const joinLock = useRef<string | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => setAppliedQuery(query.trim()), 300);
    return () => clearTimeout(timer);
  }, [query]);

  const requestKey = `${appliedQuery}|${openFilter}|${withSlots ? 'slots' : 'any'}|${retryTick}`;
  const status = result?.key === requestKey ? result.status : 'loading';
  const clans = result?.key === requestKey && result.status === 'ready' ? result.clans : [];

  useEffect(() => {
    if (!token) {
      return;
    }
    const run = ++requestSeq.current;
    api.clans
      .list(token, {
        q: appliedQuery || undefined,
        open: openFilter === 'all' ? undefined : openFilter === 'open',
        has_slots: withSlots || undefined,
      })
      .then((response) => {
        if (run !== requestSeq.current) {
          return;
        }
        setResult({ key: requestKey, status: 'ready', clans: response.clans });
      })
      .catch(() => {
        if (run !== requestSeq.current) {
          return;
        }
        setResult({ key: requestKey, status: 'error', clans: [] });
      });
  }, [token, appliedQuery, openFilter, withSlots, requestKey]);

  const joinNow = useCallback(
    async (target: Clan) => {
      if (!token || joinLock.current) {
        return;
      }
      joinLock.current = target.id;
      setBusyId(target.id);
      setJoinError(null);
      try {
        await api.clans.join(token, target.id);
        try {
          await loadClan();
        } catch {
          if (mounted.current) {
            nav.toast('Você entrou no clã. Não foi possível atualizar os dados agora.');
          }
        }
        if (mounted.current) {
          nav.replace('clan');
        }
      } catch (error) {
        if (!mounted.current) {
          return;
        }
        setJoinError(joinErrorMessage(apiErrorCode(error)));
        if (apiErrorCode(error) === 'already_member') {
          loadClan().catch(() => {
            // O clã já existe no contexto; abrir a tela refaz a leitura.
          });
        }
      } finally {
        joinLock.current = null;
        if (mounted.current) {
          setBusyId(null);
        }
      }
    },
    [token, loadClan, nav],
  );

  const searching = status === 'loading';
  const empty = status === 'ready' && clans.length === 0;
  const hasFilters = appliedQuery.length > 0 || openFilter !== 'all' || withSlots;
  const clearFilters = () => {
    setQuery('');
    setAppliedQuery('');
    setOpenFilter('all');
    setWithSlots(false);
  };

  if (!token) {
    return (
      <Page title="Descobrir clãs">
        <StateScreen
          icon="lock"
          title="Entre na sua conta"
          text="A descoberta de clãs precisa de uma sessão ativa."
          actions={
            <Btn tone="primary" go="welcome">
              Entrar
            </Btn>
          }
        />
      </Page>
    );
  }

  return (
    <Page title="Descobrir clãs">
      <Field label="Buscar clã">
        <Input
          value={query}
          onChangeText={setQuery}
          placeholder="Nome do clã ou #tag"
          maxLength={40}
          autoCorrect={false}
          autoCapitalize="none"
          returnKeyType="search"
          onSubmitEditing={() => setAppliedQuery(query.trim())}
        />
      </Field>
      {query.trim().length > 0 ? (
        <TextBtn
          muted
          onPress={() => {
            setQuery('');
            setAppliedQuery('');
          }}
        >
          Limpar busca
        </TextBtn>
      ) : null}
      <ChipRow>
        <Chip
          on={openFilter === 'open'}
          onPress={() => setOpenFilter((current) => (current === 'open' ? 'all' : 'open'))}
          accessibilityLabel="Filtrar clãs abertos"
        >
          Aberto
        </Chip>
        <Chip
          on={openFilter === 'closed'}
          onPress={() => setOpenFilter((current) => (current === 'closed' ? 'all' : 'closed'))}
          accessibilityLabel="Filtrar clãs fechados"
        >
          Fechado
        </Chip>
        <Chip
          on={withSlots}
          onPress={() => setWithSlots((current) => !current)}
          accessibilityLabel="Filtrar clãs com vaga"
        >
          Com vaga
        </Chip>
        <Chip disabled lock accessibilityLabel="Filtro por esporte indisponível">
          Esporte
        </Chip>
      </ChipRow>
      <Txt variant="tiny">Filtro por esporte ainda não disponível.</Txt>

      {joinError ? (
        <View style={{ gap: 6 }}>
          <Notice tone="orange" icon="alert">
            {joinError}
          </Notice>
          <TextBtn muted onPress={() => setJoinError(null)}>
            Dispensar
          </TextBtn>
        </View>
      ) : null}

      {searching && clans.length === 0 ? (
        <LoadingState label="Buscando clãs." variant="cards" />
      ) : null}
      {searching && clans.length > 0 ? <Txt variant="tiny">Buscando…</Txt> : null}

      {status === 'error' ? (
        <StateScreen
          icon="wifi-off"
          title="Não foi possível buscar clãs"
          text="Verifique a conexão e tente novamente."
          actions={
            <Btn tone="primary" onPress={() => setRetryTick((value) => value + 1)}>
              Tentar novamente
            </Btn>
          }
        />
      ) : null}

      {status !== 'error' && clans.length > 0
        ? // O callback só roda no toque; `joinNow` lê o lock em handler, nunca no render.
          // eslint-disable-next-line react-hooks/refs
          clans.map((clan) => {
            const isMine = myClan?.id === clan.id || clan.is_member || clan.my_role !== null;
            const full = clan.members >= clan.max_members;
            const policy = clan.join_policy;
            const busy = busyId === clan.id;
            let actionLabel = 'Solicitar';
            let actionTone: 'primary' | 'ghost' = 'ghost';
            let action: (() => void) | null = null;
            if (isMine) {
              actionLabel = 'Abrir';
              actionTone = 'primary';
              action = () => nav.replace('clan');
            } else if (full) {
              actionLabel = 'Cheio';
              action = null;
            } else if (policy === 'closed') {
              actionLabel = 'Fechado';
              action = null;
            } else if (policy === 'open') {
              actionLabel = busy ? 'Entrando…' : 'Entrar';
              actionTone = 'primary';
              action = () => void joinNow(clan);
            } else {
              actionLabel = 'Solicitar';
              action = () => nav.go('clan-join', { clanId: clan.id });
            }
            return (
              <Card key={clan.id}>
                <Row between>
                  <Row style={{ flexShrink: 1, flexWrap: 'wrap', gap: 6 }}>
                    <Badge
                      tone={policy === 'open' ? 'lime' : policy === 'approval' ? 'blue' : 'default'}
                    >
                      {joinPolicyLabel(policy)}
                    </Badge>
                    {isMine ? <Badge tone="green">Seu clã</Badge> : null}
                  </Row>
                  <Txt variant="tiny">
                    {clan.members}/{clan.max_members}
                  </Txt>
                </Row>
                <Txt variant="h2" numberOfLines={2} style={{ marginTop: 6, marginBottom: 2 }}>
                  {clan.name}
                </Txt>
                <Txt variant="tiny">{displayClanTag(clan.tag)}</Txt>
                <Row between style={{ marginTop: 12 }}>
                  <Txt variant="tiny" style={{ flexShrink: 1 }}>
                    {isMine
                      ? 'Você já participa deste clã'
                      : full
                        ? 'Sem vaga'
                        : policy === 'closed'
                          ? 'Não aceita entradas'
                          : `${Math.max(0, clan.max_members - clan.members)} vagas`}
                  </Txt>
                  <Btn
                    tone={actionTone}
                    small
                    block={false}
                    disabled={action === null || busy}
                    onPress={action ?? undefined}
                  >
                    {actionLabel}
                  </Btn>
                </Row>
              </Card>
            );
          })
        : null}

      {empty ? (
        <EmptyState
          title={hasFilters ? 'Nenhum clã com esses filtros' : 'Nenhum clã encontrado'}
          text={
            hasFilters
              ? 'Ajuste a busca ou limpe os filtros para ver todos os clãs.'
              : 'Ainda não há clãs visíveis. Você pode criar o seu.'
          }
          actions={
            <>
              {hasFilters ? (
                <Btn tone="primary" onPress={clearFilters}>
                  Limpar filtros
                </Btn>
              ) : null}
              <Btn tone={hasFilters ? 'ghost' : 'primary'} go="clan-create">
                Criar clã
              </Btn>
            </>
          }
        />
      ) : null}
    </Page>
  );
}

function ClanCreate() {
  const nav = useNav();
  const { session, loadClan } = useApp();
  const [name, setName] = useState('');
  const [tagCore, setTagCore] = useState('');
  const [description, setDescription] = useState('');
  const [busy, setBusy] = useState(false);
  const [attempted, setAttempted] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);
  const [tagError, setTagError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const submitLock = useRef(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const trimmedName = name.trim();
  const nameOk = trimmedName.length >= 3 && trimmedName.length <= 40;
  const tagOk = tagIsValid(tagCore);
  const showNameError = nameError ?? (attempted && !nameOk ? 'Use de 3 a 40 caracteres.' : null);
  const showTagError =
    tagError ??
    (tagCore.length > 0 && !tagOk ? 'Use de 2 a 7 letras ou números.' : null) ??
    (attempted && !tagOk ? 'A tag é obrigatória: 2 a 7 letras ou números.' : null);
  const canSubmit = nameOk && tagOk && !busy;

  const submit = async () => {
    setAttempted(true);
    setNameError(null);
    setTagError(null);
    setFormError(null);
    if (!nameOk || !tagOk || submitLock.current) {
      return;
    }
    if (!session) {
      nav.replace('clan');
      return;
    }
    submitLock.current = true;
    setBusy(true);
    try {
      await api.clans.create(
        session.accessToken,
        trimmedName,
        tagPayload(tagCore),
        description.trim().length > 0 ? description.trim() : null,
      );
      try {
        await loadClan();
      } catch {
        if (mounted.current) {
          nav.toast('Clã criado. Não foi possível atualizar os dados agora.');
        }
      }
      if (mounted.current) {
        nav.replace('clan');
      }
    } catch (error) {
      if (!mounted.current) {
        return;
      }
      const code = apiErrorCode(error);
      if (code === 'tag_invalid') {
        setTagError('Tag inválida: use 2 a 7 letras ou números.');
      } else if (code === 'tag_taken') {
        setTagError('Esta tag já está em uso. Escolha outra.');
      } else if (code === 'name_invalid') {
        setNameError('Nome inválido: use de 3 a 40 caracteres.');
      } else if (code === 'name_taken') {
        setNameError('Já existe um clã com este nome.');
      } else if (code === 'name_or_tag_taken') {
        setNameError('Nome ou tag já em uso.');
        setTagError('Nome ou tag já em uso.');
      } else if (code === 'already_in_clan') {
        setFormError('Você já está em um clã. Saia do atual antes de criar outro.');
      } else if (code === 'network_unavailable' || code === 'request_timeout') {
        setFormError('Sem conexão. Tente novamente.');
      } else {
        setFormError('Não foi possível criar o clã. Tente novamente.');
      }
    } finally {
      submitLock.current = false;
      if (mounted.current) {
        setBusy(false);
      }
    }
  };

  return (
    <Page title="Criar clã">
      <Field label="Nome">
        <Input
          value={name}
          onChangeText={(value) => {
            setName(value);
            setNameError(null);
          }}
          maxLength={40}
          placeholder="Nome do clã"
        />
      </Field>
      <Row between>
        <Txt variant="tiny">{trimmedName.length}/40</Txt>
        {showNameError ? (
          <Txt variant="tiny" align="right" style={{ flexShrink: 1 }}>
            {showNameError}
          </Txt>
        ) : null}
      </Row>
      <Field label="Tag">
        <InputPrefix
          input={
            <Input
              value={tagCore}
              onChangeText={(value) => {
                setTagCore(normalizeTagInput(value));
                setTagError(null);
              }}
              maxLength={7}
              autoCapitalize="characters"
              autoCorrect={false}
              placeholder="TAG"
              style={{ borderWidth: 0, borderRadius: 0, minHeight: 50 }}
            />
          }
        >
          #
        </InputPrefix>
      </Field>
      <Row between>
        <Txt variant="tiny">{`#${tagCore || '—'} · ${tagCore.length}/7`}</Txt>
        {showTagError ? (
          <Txt variant="tiny" align="right" style={{ flexShrink: 1 }}>
            {showTagError}
          </Txt>
        ) : null}
      </Row>
      <Field label="Descrição">
        <Textarea
          value={description}
          onChangeText={setDescription}
          maxLength={280}
          placeholder="O que o clã joga e onde"
        />
      </Field>
      <Txt variant="tiny">{description.length}/280</Txt>
      <Card>
        <Kv label="Entrada" value="Por aprovação" />
      </Card>
      <Notice tone="blue" icon="info">
        O clã começa com entrada por aprovação. Você pode mudar isso nas configurações.
      </Notice>
      {formError ? (
        <Notice tone="orange" icon="alert">
          {formError}
        </Notice>
      ) : null}
      <Btn tone="primary" onPress={submit} disabled={!canSubmit}>
        {busy ? 'Criando…' : 'Criar clã'}
      </Btn>
    </Page>
  );
}

type JoinFailure = { text: string; action?: 'refresh' | 'open' | 'back' };

function ClanJoin() {
  const nav = useNav();
  const { session, clan: myClan, loadClan } = useApp();
  const token = session?.accessToken ?? null;
  const clanId = typeof nav.params.clanId === 'string' ? nav.params.clanId : null;
  const [load, setLoad] = useState<{
    key: string;
    status: 'ready' | 'error';
    detail?: Clan;
  } | null>(null);
  const [loadError, setLoadError] = useState('Não foi possível carregar o clã.');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<JoinFailure | null>(null);
  const [retryTick, setRetryTick] = useState(0);
  const submitLock = useRef(false);
  const mounted = useRef(true);
  const loadKey = `${clanId ?? 'none'}|${retryTick}`;
  const status: 'loading' | 'ready' | 'error' = !clanId
    ? 'ready'
    : load?.key === loadKey
      ? load.status
      : 'loading';
  const detail = load?.key === loadKey ? (load.detail ?? null) : null;

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    if (!clanId || !token) {
      return;
    }
    let active = true;
    api.clans
      .get(token, clanId)
      .then((response) => {
        if (!active) {
          return;
        }
        setLoad({ key: loadKey, status: 'ready', detail: response });
      })
      .catch((error) => {
        if (!active) {
          return;
        }
        setLoadError(
          apiErrorCode(error) === 'not_found'
            ? 'Este clã não existe mais.'
            : 'Não foi possível carregar o clã. Verifique a conexão.',
        );
        setLoad({ key: loadKey, status: 'error' });
      });
    return () => {
      active = false;
    };
  }, [clanId, token, loadKey]);

  const isMine = !!detail && (myClan?.id === detail.id || detail.my_role !== null);
  const isFull = !!detail && detail.members >= detail.max_members;
  const isClosed = detail?.join_policy === 'closed';
  const canAsk = !!detail && !isMine && !isFull && !isClosed;
  const approval = detail?.join_policy === 'approval';

  const submit = async () => {
    if (!detail || !token || submitLock.current) {
      return;
    }
    submitLock.current = true;
    setBusy(true);
    setFailure(null);
    try {
      const result = await api.clans.join(token, detail.id, message.trim() || undefined);
      if (!mounted.current) {
        return;
      }
      if (result.status === 'joined') {
        try {
          await loadClan();
        } catch {
          // A tela de clã refaz a leitura e mostra o erro com retry.
        }
        if (mounted.current) {
          nav.replace('clan');
        }
        return;
      }
      setPending(true);
    } catch (error) {
      if (!mounted.current) {
        return;
      }
      const code = apiErrorCode(error);
      if (code === 'already_member') {
        setFailure({ text: 'Você já é membro deste clã.', action: 'open' });
      } else if (code === 'already_in_clan') {
        setFailure({
          text: 'Você já está em outro clã. Saia do atual antes de entrar em outro.',
        });
      } else if (code === 'clan_full') {
        setFailure({ text: 'Clã cheio. Volte quando abrir uma vaga.', action: 'refresh' });
      } else if (code === 'clan_cooldown') {
        setFailure({
          text: 'Você saiu de um clã há menos de 7 dias. Tente novamente mais tarde.',
        });
      } else if (code === 'clan_closed') {
        setFailure({
          text: 'Este clã não aceita mais entradas.',
          action: 'refresh',
        });
      } else if (code === 'not_found') {
        setFailure({ text: 'Este clã não existe mais.', action: 'back' });
      } else {
        setFailure({ text: joinErrorMessage(code) });
      }
    } finally {
      submitLock.current = false;
      if (mounted.current) {
        setBusy(false);
      }
    }
  };

  const runFailureAction = () => {
    if (!failure) {
      return;
    }
    if (failure.action === 'refresh') {
      setFailure(null);
      setRetryTick((value) => value + 1);
    } else if (failure.action === 'open') {
      loadClan()
        .catch(() => {
          // A tela de clã refaz a leitura; aqui só abrimos.
        })
        .finally(() => {
          if (mounted.current) {
            nav.replace('clan');
          }
        });
    } else if (failure.action === 'back') {
      nav.replace('clan-discovery');
    }
  };

  if (!clanId) {
    return (
      <Page title="Entrar em clã">
        <StateScreen
          icon="users"
          title="Clã não selecionado"
          text="Escolha um clã na descoberta para ver o resumo e solicitar entrada."
          actions={
            <>
              <Btn tone="primary" go="clan-discovery">
                Descobrir clãs
              </Btn>
              <Btn tone="ghost" back>
                Voltar
              </Btn>
            </>
          }
        />
      </Page>
    );
  }

  if (!session) {
    return (
      <Page title="Entrar em clã">
        <StateScreen
          icon="lock"
          title="Entre na sua conta"
          text="A entrada em um clã precisa de uma sessão ativa."
          actions={
            <Btn tone="primary" go="welcome">
              Entrar
            </Btn>
          }
        />
      </Page>
    );
  }

  if (status === 'loading') {
    return (
      <Page title="Entrar em clã">
        <LoadingState label="Buscando o clã." variant="clan" />
      </Page>
    );
  }

  if (status === 'error' || !detail) {
    return (
      <Page title="Entrar em clã">
        <StateScreen
          icon="wifi-off"
          title="Clã indisponível"
          text={loadError}
          actions={
            <>
              <Btn tone="primary" onPress={() => setRetryTick((value) => value + 1)}>
                Tentar novamente
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

  if (pending) {
    return (
      <Page title={detail.name}>
        <StateScreen
          icon="clock"
          title="Solicitação enviada"
          text={`Pedido enviado para ${detail.name}. A entrada depende de aprovação.`}
          actions={
            <>
              <Btn tone="primary" go="clan-discovery">
                Ver outros clãs
              </Btn>
              <Btn tone="ghost" back>
                Voltar
              </Btn>
            </>
          }
        />
      </Page>
    );
  }

  return (
    <Page title={detail.name}>
      <Card tone="ink">
        <Row between>
          <Badge tone={detail.join_policy === 'open' ? 'lime' : 'default'}>
            {joinPolicyLabel(detail.join_policy)}
          </Badge>
          <Badge>
            {detail.members}/{detail.max_members}
          </Badge>
        </Row>
        <Txt
          variant="display"
          color="onInk"
          style={{ fontSize: 28, marginTop: 10, marginBottom: 4 }}
        >
          {detail.name}
        </Txt>
        <Txt variant="tiny" color="softOnInk">
          {displayClanTag(detail.tag)} · {detail.members} de {detail.max_members} membros
        </Txt>
      </Card>
      <Card>
        <Kv label="Membros" value={`${detail.members} de ${detail.max_members}`} />
        <Kv label="Troféus" value={number(detail.trophies)} />
        <Kv label="Entrada" value={joinPolicyLabel(detail.join_policy)} />
      </Card>
      <Notice tone="blue" icon="info">
        {joinPolicyExplanation(detail.join_policy)}
      </Notice>
      {detail.description ? (
        <Card>
          <Txt variant="h3">Sobre</Txt>
          <Txt variant="sub" style={{ marginTop: 5 }}>
            {detail.description}
          </Txt>
        </Card>
      ) : null}

      {isMine ? (
        <>
          <Notice tone="green" icon="check">
            Você já participa deste clã.
          </Notice>
          <Btn tone="primary" onPress={() => nav.replace('clan')}>
            Abrir meu clã
          </Btn>
        </>
      ) : isFull ? (
        <>
          <Notice tone="orange" icon="users">
            Clã cheio. Não há vagas agora.
          </Notice>
          <Btn tone="ghost" go="clan-discovery">
            Ver outros clãs
          </Btn>
        </>
      ) : isClosed ? (
        <>
          <Notice tone="orange" icon="lock">
            Este clã não aceita novas entradas.
          </Notice>
          <Btn tone="ghost" go="clan-discovery">
            Ver outros clãs
          </Btn>
        </>
      ) : (
        <>
          {approval ? (
            <>
              <Field label="Mensagem (opcional)">
                <Textarea
                  value={message}
                  onChangeText={setMessage}
                  maxLength={200}
                  placeholder="Conte por que você quer entrar"
                />
              </Field>
              <Txt variant="tiny">{message.length}/200 · A entrada depende de aprovação.</Txt>
            </>
          ) : null}
          {failure ? (
            <View style={{ gap: 6 }}>
              <Notice tone="orange" icon="alert">
                {failure.text}
              </Notice>
              {failure.action ? (
                <TextBtn onPress={runFailureAction}>
                  {failure.action === 'refresh'
                    ? 'Atualizar clã'
                    : failure.action === 'open'
                      ? 'Abrir meu clã'
                      : 'Voltar à descoberta'}
                </TextBtn>
              ) : null}
            </View>
          ) : null}
          <Btn tone="primary" onPress={submit} disabled={busy || !canAsk}>
            {busy ? 'Enviando…' : approval ? 'Solicitar entrada' : 'Entrar no clã'}
          </Btn>
        </>
      )}
    </Page>
  );
}

function permissionError(code: string): string {
  const map: Record<string, string> = {
    owner_required: 'Só o dono do clã pode fazer isso.',
    admin_required: 'Só dono ou oficial pode remover membros.',
    cannot_remove_owner: 'O dono não pode ser removido. Transfira a liderança primeiro.',
    use_transfer: 'Para trocar o dono, use “Transferir dono”.',
    use_leave: 'Para sair do clã, use “Sair do clã”.',
    role_invalid: 'Papel inválido. Atualize a lista e tente novamente.',
    transfer_ownership_first: 'Transfira a liderança antes de sair.',
    not_found: 'Membro não encontrado. A lista foi atualizada.',
    network_unavailable: 'Sem conexão. Tente novamente.',
    request_timeout: 'A conexão demorou demais. Tente novamente.',
  };
  return map[code] ?? 'Não foi possível concluir a ação.';
}

type MemberAction = { kind: 'remove' | 'transfer'; member: ClanMember };

function ClanMembers() {
  const nav = useNav();
  const { palette } = useTheme();
  const { clan, clanMembers, session, profile, loadClan } = useApp();
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [openFor, setOpenFor] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [pending, setPending] = useState<MemberAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const runLock = useRef(false);
  const mounted = useRef(true);
  const members = useMemo(() => sortMembers(clanMembers), [clanMembers]);
  const myRole =
    clan?.my_role ?? members.find((member) => member.user_id === session?.userId)?.role ?? null;
  const amOwner = isOwnerRole(myRole);
  const canInvite = amOwner || myRole === 'admin';
  const officers = members.filter((member) => member.role === 'admin').length;
  const nameOf = (member: ClanMember) =>
    memberDisplayName(member, {
      selfUserId: session?.userId,
      selfProfileName: profile?.display_name,
    });

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const reload = useCallback(async () => {
    setStatus('loading');
    try {
      await loadClan();
      if (mounted.current) {
        setStatus('ready');
      }
    } catch {
      if (mounted.current) {
        setStatus('error');
      }
    }
  }, [loadClan]);

  useEffect(() => {
    let active = true;
    loadClan()
      .then(() => {
        if (active) {
          setStatus('ready');
        }
      })
      .catch(() => {
        if (active) {
          setStatus('error');
        }
      });
    return () => {
      active = false;
    };
  }, [loadClan]);

  const run = async (member: ClanMember, task: () => Promise<unknown>) => {
    if (!session || !clan || runLock.current) {
      return;
    }
    runLock.current = true;
    const key = `${member.user_id}:${pending?.kind ?? 'role'}`;
    setBusyKey(key);
    setError(null);
    try {
      await task();
    } catch (cause) {
      if (mounted.current) {
        setError(permissionError(apiErrorCode(cause)));
      }
      runLock.current = false;
      if (mounted.current) {
        setBusyKey(null);
      }
      return;
    }
    try {
      await loadClan();
    } catch {
      if (mounted.current) {
        setError('Ação concluída. Atualize a lista.');
      }
    }
    runLock.current = false;
    if (!mounted.current) {
      return;
    }
    setPending(null);
    setOpenFor(null);
    setBusyKey(null);
  };

  const changeRole = (member: ClanMember) => {
    if (!session || !clan) {
      return;
    }
    void run(member, () =>
      api.clans.setRole(
        session.accessToken,
        clan.id,
        member.user_id,
        member.role === 'admin' ? 'member' : 'admin',
      ),
    );
  };

  const remove = (member: ClanMember) => {
    if (!session || !clan) {
      return;
    }
    void run(member, () => api.clans.removeMember(session.accessToken, clan.id, member.user_id));
  };

  const transfer = (member: ClanMember) => {
    if (!session || !clan) {
      return;
    }
    void run(member, () => api.clans.transfer(session.accessToken, clan.id, member.user_id));
  };

  const canRemove = (member: ClanMember) =>
    member.user_id !== session?.userId &&
    member.role !== 'owner' &&
    (amOwner || (myRole === 'admin' && member.role === 'member'));

  if (status === 'loading' && members.length === 0) {
    return (
      <Page title="Membros">
        <LoadingState label="Buscando membros." variant="list" />
      </Page>
    );
  }

  if (status === 'error' && members.length === 0) {
    return (
      <Page title="Membros">
        <StateScreen
          icon="wifi-off"
          title="Não foi possível carregar os membros"
          text="Verifique a conexão e tente novamente."
          actions={
            <Btn
              tone="primary"
              onPress={() => {
                setStatus('loading');
                void reload();
              }}
            >
              Tentar novamente
            </Btn>
          }
        />
      </Page>
    );
  }

  return (
    <Page title="Membros">
      <Row between>
        <Txt variant="h3">
          {clan?.members ?? members.length} {members.length === 1 ? 'membro' : 'membros'}
        </Txt>
        <Badge>{officers} oficiais</Badge>
      </Row>
      {status === 'error' ? (
        <View style={{ gap: 6 }}>
          <Notice tone="orange" icon="alert">
            A lista pode estar desatualizada.
          </Notice>
          <TextBtn onPress={() => void reload()}>Tentar novamente</TextBtn>
        </View>
      ) : null}
      {error ? (
        <View style={{ gap: 6 }}>
          <Notice tone="orange" icon="alert">
            {error}
          </Notice>
          <TextBtn onPress={() => void reload()}>Atualizar lista</TextBtn>
        </View>
      ) : null}
      {members.length === 0 ? (
        <Card>
          <Txt variant="tiny">Nenhum membro para mostrar.</Txt>
        </Card>
      ) : null}
      <CardList>
        {members.map((member, index) => {
          const expanded = openFor === member.user_id;
          const last = index === members.length - 1;
          const manageable = amOwner || canRemove(member);
          const isPendingThis = pending?.member.user_id === member.user_id;
          const busyRemove = busyKey === `${member.user_id}:remove`;
          const busyTransfer = busyKey === `${member.user_id}:transfer`;
          const busyRole = busyKey === `${member.user_id}:role`;
          return (
            <View key={member.user_id}>
              <ListRow last={!expanded && last}>
                <IdentityBadge
                  size={34}
                  identity={identityFromSeed(member.user_id)}
                  palette={palette}
                />
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                    {nameOf(member)}
                  </Text>
                  <Text style={{ fontSize: 13, color: palette.muted }}>
                    {member.user_id === session?.userId
                      ? `Você · ${myRoleLabel(member.role)}`
                      : myRoleLabel(member.role)}
                  </Text>
                </View>
                <Badge
                  tone={
                    member.role === 'owner' ? 'lime' : member.role === 'admin' ? 'blue' : 'default'
                  }
                >
                  {myRoleLabel(member.role).toUpperCase()}
                </Badge>
                {manageable ? (
                  <IconBtn
                    icon="more"
                    label={`Ações de ${nameOf(member)}`}
                    plain
                    onPress={() => {
                      setError(null);
                      setPending(null);
                      setOpenFor((current) => (current === member.user_id ? null : member.user_id));
                    }}
                  />
                ) : null}
              </ListRow>
              {expanded ? (
                <View
                  style={{
                    paddingHorizontal: 18,
                    paddingBottom: 14,
                    gap: 8,
                    borderBottomWidth: last ? 0 : 1,
                    borderBottomColor: palette.line,
                  }}
                >
                  {isPendingThis ? (
                    <>
                      <Notice tone="orange" icon="alert">
                        {pending?.kind === 'transfer'
                          ? `Você deixará de ser Dono. ${nameOf(member)} passará a ser Dono.`
                          : `Remover ${nameOf(member)} do clã? A pessoa perde o acesso ao chat e às ações do clã.`}
                      </Notice>
                      <BtnRow>
                        <Btn tone="ghost" onPress={() => setPending(null)}>
                          Cancelar
                        </Btn>
                        <Btn
                          tone="danger"
                          disabled={busyRemove || busyTransfer}
                          onPress={() =>
                            pending?.kind === 'transfer' ? transfer(member) : remove(member)
                          }
                        >
                          {pending?.kind === 'transfer'
                            ? busyTransfer
                              ? 'Transferindo…'
                              : 'Transferir'
                            : busyRemove
                              ? 'Removendo…'
                              : 'Remover'}
                        </Btn>
                      </BtnRow>
                    </>
                  ) : (
                    <>
                      {amOwner && member.role !== 'owner' ? (
                        <Btn tone="soft" disabled={busyRole} onPress={() => changeRole(member)}>
                          {member.role === 'admin'
                            ? busyRole
                              ? 'Rebaixando…'
                              : 'Rebaixar para Membro'
                            : busyRole
                              ? 'Promovendo…'
                              : 'Promover a Oficial'}
                        </Btn>
                      ) : null}
                      {amOwner && member.user_id !== session?.userId ? (
                        <Btn
                          tone="soft"
                          disabled={busyRole}
                          onPress={() => setPending({ kind: 'transfer', member })}
                        >
                          Transferir dono para {nameOf(member)}
                        </Btn>
                      ) : null}
                      {canRemove(member) ? (
                        <Btn tone="danger" onPress={() => setPending({ kind: 'remove', member })}>
                          Remover do clã
                        </Btn>
                      ) : null}
                    </>
                  )}
                </View>
              ) : null}
            </View>
          );
        })}
      </CardList>
      {canInvite ? (
        <Btn tone="primary" icon="plus" go="clan-invite">
          Convidar membros
        </Btn>
      ) : null}
      <Notice tone="blue" icon="info">
        Dono e oficiais podem remover membros. O dono pode transferir a liderança.
      </Notice>
      <TextBtn muted onPress={() => nav.back()}>
        Voltar
      </TextBtn>
    </Page>
  );
}

type ClanDraftState = {
  name: string;
  description: string;
  join_policy: string;
};

/**
 * Rascunho da edição sobrevive à troca de aba. O app só mantém montada a pilha
 * da aba ativa; este cache em memória (sem persistência) devolve o rascunho ao
 * reabrir a mesma tela. Nunca contém tag: é o mesmo formato do PATCH.
 */
let clanSettingsDraft: {
  clanId: string;
  draft: ClanDraftState;
  base: ClanDraftState;
} | null = null;

function ClanPolicyOption({
  label,
  explanation,
  selected,
  disabled,
  onPress,
}: {
  label: string;
  explanation: string;
  selected: boolean;
  disabled: boolean;
  onPress: () => void;
}) {
  const { palette } = useTheme();
  return (
    <Pressable
      accessibilityRole="radio"
      accessibilityState={{ selected, disabled }}
      accessibilityLabel={`${label}. ${explanation}`}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => ({
        minHeight: 56,
        flexDirection: 'row',
        alignItems: 'center',
        gap: 10,
        borderWidth: selected ? 2 : 1.5,
        borderColor: selected ? palette.ink : palette.lineStrong,
        borderRadius: 12,
        backgroundColor: selected ? palette.surface2 : palette.surface,
        paddingHorizontal: selected ? 11 : 12,
        paddingVertical: 10,
        opacity: disabled ? 0.55 : pressed ? 0.9 : 1,
      })}
    >
      <View
        style={{
          width: 22,
          height: 22,
          borderRadius: 11,
          borderWidth: 1.5,
          borderColor: selected ? palette.ink : palette.lineStrong,
          backgroundColor: selected ? palette.lime : 'transparent',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {selected ? <Icon name="check" size={14} color={palette.ink} /> : null}
      </View>
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 14, lineHeight: 18, fontWeight: '800', color: palette.ink }}>
          {label}
        </Text>
        <Text style={{ fontSize: 13, lineHeight: 18, color: palette.muted }}>{explanation}</Text>
      </View>
    </Pressable>
  );
}

function ClanSettings() {
  const nav = useNav();
  const { clan, session, loadClan, setClan } = useApp();
  const cached = clan && clanSettingsDraft?.clanId === clan.id ? clanSettingsDraft : null;
  const initialDraft =
    cached?.draft ??
    (clan
      ? {
          name: clan.name,
          description: clan.description ?? '',
          join_policy: clan.join_policy,
        }
      : null);
  const initialBase = cached?.base ?? initialDraft;
  const [name, setName] = useState(initialDraft?.name ?? '');
  const [description, setDescription] = useState(initialDraft?.description ?? '');
  const [policy, setPolicy] = useState(initialDraft?.join_policy ?? 'approval');
  const [base, setBase] = useState<ClanDraftState | null>(initialBase);
  const [attempted, setAttempted] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [discardOpen, setDiscardOpen] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const [fetching, setFetching] = useState(!clan);
  const [confirmLeave, setConfirmLeave] = useState(false);
  const [leaveBusy, setLeaveBusy] = useState(false);
  const [leaveError, setLeaveError] = useState<string | null>(null);
  const [retryTick, setRetryTick] = useState(0);
  const saveLock = useRef(false);
  const leaveLock = useRef(false);
  const initializedFor = useRef<string | null>(clan?.id ?? null);
  const mounted = useRef(true);
  const canEdit = isAdminRole(clan?.my_role);
  const isOwner = isOwnerRole(clan?.my_role);
  const nameValue = name.trim();
  const descriptionValue = description.trim();
  const nameValid = nameValue.length >= 3 && nameValue.length <= 40;
  const dirty =
    !!base &&
    (nameValue !== base.name.trim() ||
      descriptionValue !== base.description.trim() ||
      policy !== base.join_policy);
  const canSave = canEdit && dirty && nameValid && !saving;
  const shownNameError =
    nameError ??
    ((attempted || dirty) && !nameValid
      ? nameValue.length === 0
        ? 'Informe o nome do clã.'
        : 'Use de 3 a 40 caracteres.'
      : null);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    if (clan) {
      return;
    }
    loadClan()
      .then(() => {
        if (active) {
          setFetching(false);
        }
      })
      .catch(() => {
        if (active) {
          setFetching(false);
          setLoadFailed(true);
        }
      });
    return () => {
      active = false;
    };
  }, [clan, loadClan, retryTick]);

  useEffect(() => {
    if (!clan || initializedFor.current === clan.id) {
      return;
    }
    initializedFor.current = clan.id;
    const next = {
      name: clan.name,
      description: clan.description ?? '',
      join_policy: clan.join_policy,
    };
    setName(next.name);
    setDescription(next.description);
    setPolicy(next.join_policy);
    setBase(next);
  }, [clan]);

  useEffect(() => {
    if (!clan || !base || !dirty) {
      clanSettingsDraft = null;
      return;
    }
    clanSettingsDraft = {
      clanId: clan.id,
      draft: { name, description, join_policy: policy },
      base,
    };
  }, [clan, base, dirty, name, description, policy]);

  const requestExit = useCallback(() => {
    if (saving) {
      return;
    }
    if (dirty) {
      setDiscardOpen(true);
      return;
    }
    nav.back();
  }, [dirty, nav, saving]);

  useEffect(() => {
    if (!dirty || nav.id !== 'clan-settings') {
      return;
    }
    const subscription = BackHandler.addEventListener('hardwareBackPress', () => {
      setDiscardOpen(true);
      return true;
    });
    return () => subscription.remove();
  }, [dirty, nav.id]);

  const leave = async () => {
    if (!session || !clan || leaveLock.current) {
      return;
    }
    leaveLock.current = true;
    setLeaveBusy(true);
    setLeaveError(null);
    try {
      await api.clans.leave(session.accessToken, clan.id);
      try {
        await loadClan();
      } catch {
        if (mounted.current) {
          nav.toast('Você saiu do clã. Não foi possível atualizar os dados agora.');
        }
      }
      if (mounted.current) {
        nav.replace('clan');
      }
    } catch (cause) {
      if (mounted.current) {
        const code = apiErrorCode(cause);
        setLeaveError(permissionError(code));
        if (code === 'transfer_ownership_first') {
          loadClan().catch(() => {
            // A tela de membros recarrega o papel real ao abrir.
          });
        }
      }
    } finally {
      leaveLock.current = false;
      if (mounted.current) {
        setLeaveBusy(false);
      }
    }
  };

  const save = async () => {
    setAttempted(true);
    if (!clan || !session || !base || !canEdit || !nameValid || saveLock.current) {
      return;
    }
    const patch = clanUpdatePatch(base, {
      name,
      description,
      join_policy: policy,
    });
    if (Object.keys(patch).length === 0) {
      return;
    }
    saveLock.current = true;
    setSaving(true);
    setError(null);
    setNameError(null);
    try {
      const updated = await api.clans.update(session.accessToken, clan.id, patch);
      if (!mounted.current) {
        return;
      }
      setClan(updated);
      const next = {
        name: updated.name,
        description: updated.description ?? '',
        join_policy: updated.join_policy,
      };
      setName(next.name);
      setDescription(next.description);
      setPolicy(next.join_policy);
      setBase(next);
      setAttempted(false);
      clanSettingsDraft = null;
      nav.toast('Clã atualizado.');
      AccessibilityInfo.announceForAccessibility('Clã atualizado');
    } catch (cause) {
      if (!mounted.current) {
        return;
      }
      const code = apiErrorCode(cause);
      const forbidden =
        (cause instanceof ApiError && cause.status === 403) ||
        code === 'owner_required' ||
        code === 'admin_required';
      if (code === 'name_taken' || code === 'name_or_tag_taken') {
        setNameError('Já existe um clã com esse nome.');
      } else if (code === 'name_invalid') {
        setNameError('Use de 3 a 40 caracteres.');
      } else if (code === 'description_invalid') {
        setError('A descrição deve ter até 280 caracteres.');
      } else if (code === 'join_policy_invalid') {
        setError('Escolha uma entrada válida.');
      } else if (forbidden) {
        setError('Só o Dono e os Oficiais podem editar o clã.');
        loadClan().catch(() => {
          // A tela mantém o rascunho e volta à leitura quando o clã recarrega.
        });
      } else {
        setError('Não foi possível salvar. Tente de novo.');
      }
    } finally {
      saveLock.current = false;
      if (mounted.current) {
        setSaving(false);
      }
    }
  };

  const discard = () => {
    setDiscardOpen(false);
    clanSettingsDraft = null;
    if (base) {
      setName(base.name);
      setDescription(base.description);
      setPolicy(base.join_policy);
    }
    nav.back();
  };

  if (!clan) {
    if (loadFailed) {
      return (
        <Page title="Configurações do clã">
          <StateScreen
            icon="wifi-off"
            title="Não foi possível carregar o clã"
            text="Verifique a conexão e tente novamente."
            actions={
              <Btn
                tone="primary"
                onPress={() => {
                  setLoadFailed(false);
                  setFetching(true);
                  setRetryTick((value) => value + 1);
                }}
              >
                Tentar novamente
              </Btn>
            }
          />
        </Page>
      );
    }
    if (!fetching) {
      return (
        <Page title="Configurações do clã">
          <EmptyState
            title="Você não está em um clã"
            text="Entre em um clã ou crie o seu para acessar as configurações."
            actions={
              <Btn tone="primary" go="clan-discovery">
                Descobrir clãs
              </Btn>
            }
          />
        </Page>
      );
    }
    return (
      <Page title="Configurações do clã">
        <LoadingState label="Buscando seu clã." variant="clan" />
      </Page>
    );
  }

  return (
    <Page title="Configurações do clã" onBack={requestExit}>
      <Card>
        <Row between>
          <Txt variant="h2" numberOfLines={2} style={{ flex: 1 }}>
            {clan.name}
          </Txt>
          <Badge tone={clan.join_policy === 'open' ? 'lime' : 'default'}>
            {joinPolicyLabel(clan.join_policy)}
          </Badge>
        </Row>
        <Txt variant="tiny" style={{ marginTop: 4 }}>
          {clan.members}/{clan.max_members} membros · {number(clan.trophies)} troféus
        </Txt>
        <Txt variant="sub" style={{ marginTop: 8 }}>
          {joinPolicyExplanation(clan.join_policy)}
        </Txt>
      </Card>

      <Card>
        <View accessible accessibilityLabel="Tag do clã, não editável">
          <Row between>
            <Txt variant="tiny">Tag</Txt>
            <Txt variant="h3">{displayClanTag(clan.tag)}</Txt>
          </Row>
          <Txt variant="tiny" style={{ marginTop: 4 }}>
            A tag não pode ser alterada.
          </Txt>
        </View>
      </Card>

      {canEdit ? (
        <>
          <Field label="Nome do clã">
            <Input
              value={name}
              onChangeText={(value) => {
                setName(value);
                setNameError(null);
                setError(null);
              }}
              maxLength={40}
              placeholder="Nome do clã"
              autoCorrect={false}
              accessibilityLabel="Nome do clã"
            />
          </Field>
          <Row between>
            <Txt variant="tiny">{`${name.length}/40`}</Txt>
            {shownNameError ? (
              <Txt variant="tiny" color="red" align="right" style={{ flexShrink: 1 }}>
                {shownNameError}
              </Txt>
            ) : null}
          </Row>
          <Field label="Descrição">
            <Textarea
              value={description}
              onChangeText={(value) => {
                setDescription(value);
                setError(null);
              }}
              maxLength={280}
              placeholder="O que o clã joga e onde"
              accessibilityLabel="Descrição do clã"
            />
          </Field>
          <Txt variant="tiny">{`${description.length}/280`}</Txt>
          <Field label="Entrada no clã">
            <View style={{ gap: 8 }}>
              <ClanPolicyOption
                label="Aberto"
                explanation="Qualquer pessoa entra na hora."
                selected={policy === 'open'}
                disabled={saving}
                onPress={() => {
                  setPolicy('open');
                  setError(null);
                }}
              />
              <ClanPolicyOption
                label="Aprovação"
                explanation="Você aprova cada pedido de entrada."
                selected={policy === 'approval'}
                disabled={saving}
                onPress={() => {
                  setPolicy('approval');
                  setError(null);
                }}
              />
              <ClanPolicyOption
                label="Fechado"
                explanation="Só entra quem recebe convite."
                selected={policy === 'closed'}
                disabled={saving}
                onPress={() => {
                  setPolicy('closed');
                  setError(null);
                }}
              />
            </View>
          </Field>
          {error ? (
            <Notice tone="orange" icon="alert">
              {error}
            </Notice>
          ) : null}
          <Btn tone="primary" onPress={() => void save()} disabled={!canSave}>
            {saving ? 'Salvando.' : 'Salvar alterações'}
          </Btn>
        </>
      ) : (
        <>
          <Notice tone="blue" icon="shield">
            Só o Dono e os Oficiais podem editar o clã.
          </Notice>
          <Card>
            <Kv label="Nome" value={clan.name} />
            <Kv label="Descrição" value={clan.description ?? 'Sem descrição.'} />
            <Kv label="Entrada" value={joinPolicyLabel(clan.join_policy)} />
          </Card>
        </>
      )}

      <Btn tone="primary" go="clan-members">
        Membros e cargos
      </Btn>
      {leaveError ? (
        <Notice tone="orange" icon="alert">
          {leaveError}
        </Notice>
      ) : null}
      {isOwner ? (
        <>
          <Notice tone="orange" icon="shield">
            Você é Dono. Transfira a liderança antes de sair do clã.
          </Notice>
          <Btn tone="ghost" go="clan-members">
            Transferir dono
          </Btn>
          <Btn tone="ghost" disabled>
            Sair do clã
          </Btn>
        </>
      ) : confirmLeave ? (
        <>
          <Notice tone="orange" icon="alert">
            Você sairá do clã {clan.name} e não verá mais o chat.
          </Notice>
          <BtnRow>
            <Btn tone="ghost" onPress={() => setConfirmLeave(false)}>
              Ficar no clã
            </Btn>
            <Btn tone="danger" onPress={leave} disabled={leaveBusy}>
              {leaveBusy ? 'Saindo…' : 'Sair do clã'}
            </Btn>
          </BtnRow>
        </>
      ) : (
        <Btn tone="ghost" onPress={() => setConfirmLeave(true)}>
          Sair do clã
        </Btn>
      )}

      <BottomSheetFrame
        visible={discardOpen}
        onClose={() => setDiscardOpen(false)}
        title="Descartar alterações?"
        subtitle="Você alterou o clã e ainda não salvou."
        accessibilityLabel="Descartar alterações"
        footer={
          <BtnRow>
            <Btn tone="primary" onPress={() => setDiscardOpen(false)}>
              Continuar editando
            </Btn>
            <Btn tone="danger" onPress={discard}>
              Descartar
            </Btn>
          </BtnRow>
        }
      />
    </Page>
  );
}

function ClanReportFooter({
  count,
  busy,
  disabled,
  onConfirm,
}: {
  count: number;
  busy: boolean;
  disabled: boolean;
  onConfirm: () => void;
}) {
  const close = useSheetClose();
  return (
    <BtnRow>
      <Btn tone="ghost" disabled={busy} onPress={() => close()}>
        Cancelar
      </Btn>
      <Btn tone="primary" disabled={busy || disabled || count === 0} onPress={onConfirm}>
        {busy ? 'Enviando…' : `Denunciar (${count})`}
      </Btn>
    </BtnRow>
  );
}

function ClanChat() {
  const nav = useNav();
  const { palette } = useTheme();
  const { clan, clanMessages, session, loadClanMessages, loadClan } = useApp();
  const clanId = clan?.id ?? null;
  const [draft, setDraft] = useState('');
  const [localRows, setLocalRows] = useState<ChatRow[]>([]);
  const [load, setLoad] = useState<{ key: string; status: 'ready' | 'error' } | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState(false);
  const [retryTick, setRetryTick] = useState(0);
  const [selecting, setSelecting] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [reportOpen, setReportOpen] = useState(false);
  const [reason, setReason] = useState('');
  const [reporting, setReporting] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);
  const [reportNotice, setReportNotice] = useState<string | null>(null);
  const listRef = useRef<FlatList<ChatRow>>(null);
  const atBottom = useRef(true);
  const didInitialScroll = useRef(false);
  const localSeq = useRef(0);
  const draftRef = useRef('');
  const delivering = useRef<Set<string>>(new Set());
  const refreshingLock = useRef(false);
  const mounted = useRef(true);
  const reportLock = useRef(false);
  const longPressGuard = useRef(0);
  const loadKey = `${clanId ?? 'none'}|${retryTick}`;
  const status: 'loading' | 'ready' | 'error' = !session
    ? 'ready'
    : load?.key === loadKey
      ? load.status
      : 'loading';

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  // Abertura: se o clã já está no contexto, apenas 1 GET de mensagens. Sem clã
  // no contexto, `loadClan` busca clã + membros + mensagens de uma vez.
  useEffect(() => {
    if (!session) {
      return;
    }
    let active = true;
    const request = clanId ? loadClanMessages(clanId) : loadClan();
    request
      .then(() => {
        if (active) {
          setLoad({ key: loadKey, status: 'ready' });
        }
      })
      .catch(() => {
        if (active) {
          setLoad({ key: loadKey, status: 'error' });
        }
      });
    return () => {
      active = false;
    };
  }, [session, clanId, loadKey, loadClan, loadClanMessages]);

  const rows = useMemo(() => mergeChatRows(clanMessages, localRows), [clanMessages, localRows]);
  const selectedMessages = useMemo(
    () =>
      selectedIds.filter((id) =>
        rows.some((row) => row.serverId === id && isReportableMessage(row)),
      ),
    [rows, selectedIds],
  );

  const scrollToEnd = (animated: boolean) => {
    requestAnimationFrame(() => listRef.current?.scrollToEnd({ animated }));
  };

  const deliver = async (localKey: string, body: string) => {
    if (!session || !clanId || delivering.current.has(localKey)) {
      return;
    }
    delivering.current.add(localKey);
    setLocalRows((current) =>
      current.map((row) => (row.key === localKey ? { ...row, status: 'sending' } : row)),
    );
    try {
      const saved = await api.clans.sendMessage(session.accessToken, clanId, body);
      if (!mounted.current) {
        return;
      }
      setLocalRows((current) =>
        current.map((row) =>
          row.key === localKey
            ? {
                ...row,
                key: saved.id,
                serverId: saved.id,
                status: 'sent',
                body: saved.body,
                createdAt: saved.created_at,
                displayName: saved.display_name,
              }
            : row,
        ),
      );
      AccessibilityInfo.announceForAccessibility('Mensagem enviada');
    } catch (error) {
      if (!mounted.current) {
        return;
      }
      const code = apiErrorCode(error);
      const errorText =
        code === 'body_invalid'
          ? 'Mensagem vazia ou acima de 2000 caracteres.'
          : code === 'network_unavailable' || code === 'request_timeout'
            ? 'Sem conexão. Tente de novo.'
            : code === 'invalid_token' || code === 'session_expired'
              ? 'Sessão expirada. Entre novamente.'
              : 'Não enviada';
      setLocalRows((current) =>
        current.map((row) =>
          row.key === localKey ? { ...row, status: 'failed', errorText } : row,
        ),
      );
      AccessibilityInfo.announceForAccessibility('Falha ao enviar. Toque em tentar de novo.');
    } finally {
      delivering.current.delete(localKey);
    }
  };

  const send = () => {
    // Lê do ref: dois toques no mesmo frame não duplicam o mesmo texto, mesmo
    // antes do re-render que limpa o campo.
    const body = draftRef.current.trim();
    if (!body || !session || !clanId) {
      return;
    }
    const localKey = `local-${(localSeq.current += 1)}`;
    const row: ChatRow = {
      key: localKey,
      serverId: null,
      senderId: session.userId,
      displayName: 'Você',
      body,
      createdAt: new Date().toISOString(),
      status: 'sending',
    };
    // Otimista: a bolha entra e o campo esvazia antes do POST. A lista não é
    // recarregada; a reconciliação é feita pelo id retornado.
    setLocalRows((current) => [...current, row]);
    draftRef.current = '';
    setDraft('');
    atBottom.current = true;
    void deliver(localKey, body);
  };

  const refresh = async () => {
    if (!session || refreshingLock.current) {
      return;
    }
    refreshingLock.current = true;
    setRefreshing(true);
    setRefreshError(false);
    try {
      if (clanId) {
        await loadClanMessages(clanId);
      } else {
        await loadClan();
      }
    } catch {
      if (mounted.current) {
        setRefreshError(true);
      }
    } finally {
      refreshingLock.current = false;
      if (mounted.current) {
        setRefreshing(false);
      }
    }
  };

  const exitSelection = useCallback(() => {
    setSelecting(false);
    setSelectedIds([]);
    setReportOpen(false);
    setReason('');
    setReportError(null);
    setReportNotice(null);
  }, []);

  const cancelSelection = useCallback(() => {
    if (reporting) {
      return;
    }
    exitSelection();
    AccessibilityInfo.announceForAccessibility('Seleção cancelada.');
  }, [exitSelection, reporting]);

  const enterSelection = (row: ChatRow) => {
    const serverId = row.serverId;
    if (!serverId || !isReportableMessage(row)) {
      return;
    }
    // O toque de soltura depois do long press não pode desmarcar na hora.
    longPressGuard.current = Date.now();
    setSelecting(true);
    setSelectedIds([serverId]);
    setReportNotice(null);
    AccessibilityInfo.announceForAccessibility('Modo de seleção. 1 mensagem selecionada.');
  };

  const toggleSelection = (row: ChatRow) => {
    if (Date.now() - longPressGuard.current < 500) {
      return;
    }
    const serverId = row.serverId;
    if (!serverId || !isReportableMessage(row)) {
      return;
    }
    const wasSelected = selectedMessages.includes(serverId);
    setSelectedIds((current) =>
      current.includes(serverId) ? current.filter((id) => id !== serverId) : [...current, serverId],
    );
    AccessibilityInfo.announceForAccessibility(
      wasSelected ? 'Mensagem removida da seleção.' : 'Mensagem selecionada.',
    );
  };

  useEffect(() => {
    if (!selecting || nav.id !== 'clan-chat') {
      return;
    }
    // O Shell também escuta o back. Registrar no próximo tick garante que o
    // nosso listener fique por último (o BackHandler chama em ordem inversa) e
    // saia da seleção antes de qualquer pop de tela.
    let subscription: { remove: () => void } | null = null;
    const timer = setTimeout(() => {
      subscription = BackHandler.addEventListener('hardwareBackPress', () => {
        if (reportOpen) {
          setReportOpen(false);
          return true;
        }
        cancelSelection();
        return true;
      });
    }, 0);
    return () => {
      clearTimeout(timer);
      subscription?.remove();
    };
  }, [selecting, reportOpen, cancelSelection, nav.id]);

  const openReport = () => {
    if (selectedMessages.length === 0 || reporting) {
      return;
    }
    setReportOpen(true);
    setReportError(null);
  };

  const submitReport = async () => {
    const trimmed = reason.trim();
    if (
      !session ||
      !clanId ||
      selectedMessages.length === 0 ||
      reportLock.current ||
      trimmed.length === 0
    ) {
      if (trimmed.length === 0) {
        setReportError('Descreva o motivo da denúncia.');
      }
      return;
    }
    const targets = [...selectedMessages];
    reportLock.current = true;
    setReporting(true);
    setReportError(null);
    let sent = 0;
    const failed: string[] = [];
    for (const messageId of targets) {
      try {
        await api.clans.reportMessage(session.accessToken, clanId, messageId, trimmed);
        sent += 1;
      } catch (error) {
        // 409/duplicada: a mensagem já tinha denúncia deste usuário.
        const duplicate = error instanceof ApiError && isDuplicateReport(error);
        if (!duplicate) {
          failed.push(messageId);
        }
      }
    }
    reportLock.current = false;
    if (!mounted.current) {
      return;
    }
    setReporting(false);

    if (failed.length === 0) {
      exitSelection();
      const message =
        sent === 0
          ? 'Essas mensagens já foram denunciadas.'
          : sent === 1
            ? 'Denúncia enviada.'
            : `${sent} denúncias enviadas.`;
      nav.toast(message);
      AccessibilityInfo.announceForAccessibility(message);
      return;
    }

    setSelectedIds(failed);
    setReportOpen(false);
    const details = failed.slice(0, 3).map((messageId) => {
      const row = rows.find((item) => item.serverId === messageId);
      if (!row) {
        return 'mensagem';
      }
      const preview = row.body.length > 24 ? `${row.body.slice(0, 24)}…` : row.body;
      const time = row.createdAt ? ` (${row.createdAt.slice(11, 16)})` : '';
      return `${preview}${time}`;
    });
    const extra = failed.length > 3 ? `; +${failed.length - 3}` : '';
    const summary = `${failed.length} de ${targets.length} não ${failed.length === 1 ? 'foi denunciada' : 'foram denunciadas'}: ${details.join('; ')}${extra}.`;
    setReportNotice(summary);
    nav.toast('Algumas denúncias não foram enviadas.');
    AccessibilityInfo.announceForAccessibility(summary);
  };

  const renderRow = ({ item }: { item: ChatRow }) => {
    const mine = item.senderId === session?.userId;
    const reportable = isReportableMessage(item);
    const isSelected = !!item.serverId && selectedIds.includes(item.serverId);
    const author = mine ? 'Você' : item.displayName?.trim() || 'Membro';
    const bubbleStyle = {
      alignSelf: mine ? ('flex-end' as const) : ('flex-start' as const),
      maxWidth: '88%' as const,
      paddingHorizontal: 12,
      paddingVertical: 10,
      borderRadius: 18,
      borderWidth: isSelected ? 2 : 1.5,
      borderColor: isSelected ? palette.ink : palette.line,
      backgroundColor: mine ? palette.limeSoft : palette.surface,
    };
    const content = (
      <>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
          {selecting && reportable ? (
            <View
              importantForAccessibility="no"
              accessibilityElementsHidden
              style={{
                width: 20,
                height: 20,
                borderRadius: 5,
                borderWidth: 2,
                borderColor: isSelected ? palette.ink : palette.line,
                backgroundColor: isSelected ? palette.ink : 'transparent',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {isSelected ? <Icon name="check" size={12} color={palette.onInk} /> : null}
            </View>
          ) : null}
          <IdentityBadge size={24} identity={identityFromSeed(item.senderId)} palette={palette} />
          <Txt variant="tiny">
            <Text style={{ fontWeight: '800', color: palette.ink }}>{author}</Text>
            {item.createdAt ? ` · ${item.createdAt.slice(11, 16)}` : ''}
          </Txt>
        </View>
        <Text style={{ marginTop: 3, fontSize: 14, color: palette.ink }}>{item.body}</Text>
        {item.status === 'sending' ? (
          <Text
            accessibilityLiveRegion="polite"
            style={{ marginTop: 4, fontSize: 11, color: palette.muted }}
          >
            Enviando…
          </Text>
        ) : null}
        {item.status === 'failed' ? (
          <View style={{ marginTop: 2 }}>
            <Text accessibilityLiveRegion="polite" style={{ fontSize: 11, color: palette.muted }}>
              {item.errorText ?? 'Não enviada'}
            </Text>
            <TextBtn muted onPress={() => void deliver(item.key, item.body)}>
              Tentar de novo
            </TextBtn>
          </View>
        ) : null}
      </>
    );

    if (!reportable) {
      return (
        <View style={[bubbleStyle, item.status === 'sending' ? { opacity: 0.75 } : null]}>
          {content}
        </View>
      );
    }

    return (
      <Pressable
        onLongPress={selecting ? undefined : () => enterSelection(item)}
        onPress={selecting ? () => toggleSelection(item) : undefined}
        delayLongPress={350}
        accessibilityRole="button"
        accessibilityLabel={`${author}: ${item.body}`}
        accessibilityHint={
          selecting ? 'Toque para marcar ou desmarcar.' : 'Pressione e segure para denunciar.'
        }
        accessibilityState={{ selected: isSelected }}
        accessibilityActions={[{ name: 'report', label: 'Denunciar mensagem' }]}
        onAccessibilityAction={(event) => {
          if (event.nativeEvent.actionName === 'report') {
            enterSelection(item);
          }
        }}
        style={({ pressed }) => [bubbleStyle, { opacity: pressed ? 0.92 : 1 }]}
      >
        {content}
      </Pressable>
    );
  };

  if (status === 'loading') {
    return (
      <Page title="Chat do clã">
        <LoadingState label="Buscando mensagens." variant="social" />
      </Page>
    );
  }

  if (status === 'error') {
    return (
      <Page title="Chat do clã">
        <StateScreen
          icon="wifi-off"
          title="Não foi possível abrir o chat"
          text="Verifique a conexão e tente novamente."
          actions={
            <Btn tone="primary" onPress={() => setRetryTick((value) => value + 1)}>
              Tentar novamente
            </Btn>
          }
        />
      </Page>
    );
  }

  if (!clan) {
    return (
      <Page title="Chat do clã">
        <EmptyState
          title="Você ainda não tem clã"
          text="Entre em um clã para conversar com o grupo."
          actions={
            <Btn tone="primary" go="clan-discovery">
              Descobrir clãs
            </Btn>
          }
        />
      </Page>
    );
  }

  return (
    <Page title={clan.name} scroll={false}>
      <Card tone="flat" padding={9}>
        <Row between wrap gap={6}>
          <Txt variant="tiny" style={{ flexShrink: 1, minWidth: 0 }}>
            {clan.members} membros · chat permanente
          </Txt>
          <Badge tone="green">SÓ MEMBROS</Badge>
        </Row>
        {selecting ? null : (
          <Txt variant="tiny" style={{ marginTop: 6 }}>
            Pressione e segure uma mensagem para denunciar.
          </Txt>
        )}
      </Card>
      {refreshError ? (
        <View style={{ gap: 4 }}>
          <Notice tone="orange" icon="alert">
            Não foi possível atualizar as mensagens.
          </Notice>
          <TextBtn muted onPress={() => void refresh()}>
            Tentar novamente
          </TextBtn>
        </View>
      ) : null}
      {selecting ? (
        <Card tone="flat" padding={10}>
          <Text
            accessibilityLiveRegion="polite"
            style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}
          >
            {selectedMessages.length === 0
              ? 'Nenhuma mensagem selecionada'
              : selectedMessages.length === 1
                ? '1 mensagem selecionada'
                : `${selectedMessages.length} mensagens selecionadas`}
          </Text>
          <Txt variant="tiny" style={{ marginTop: 2 }}>
            Toque nas mensagens para marcar ou desmarcar.
          </Txt>
          <View style={{ marginTop: 8 }}>
            <BtnRow>
              <Btn tone="ghost" disabled={reporting} onPress={cancelSelection}>
                Cancelar
              </Btn>
              <Btn
                tone="primary"
                disabled={selectedMessages.length === 0 || reporting}
                onPress={openReport}
              >
                {`Denunciar (${selectedMessages.length})`}
              </Btn>
            </BtnRow>
          </View>
        </Card>
      ) : null}
      {reportNotice ? (
        <View style={{ gap: 6 }}>
          <Notice tone="orange" icon="alert">
            {reportNotice}
          </Notice>
          <TextBtn onPress={openReport}>Tentar de novo</TextBtn>
        </View>
      ) : null}
      <FlatList
        ref={listRef}
        data={rows}
        extraData={`${selecting}:${selectedIds.join(',')}`}
        keyExtractor={(item) => item.key}
        renderItem={renderRow}
        style={{ flex: 1 }}
        contentContainerStyle={{ gap: 10, paddingBottom: 6 }}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
        onScroll={(event) => {
          const { contentOffset, contentSize, layoutMeasurement } = event.nativeEvent;
          atBottom.current = contentOffset.y + layoutMeasurement.height >= contentSize.height - 56;
        }}
        scrollEventThrottle={32}
        onContentSizeChange={() => {
          if (!atBottom.current) {
            return;
          }
          scrollToEnd(didInitialScroll.current);
          didInitialScroll.current = true;
        }}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => void refresh()}
            tintColor={palette.ink}
            colors={[palette.ink]}
          />
        }
        ListEmptyComponent={
          <Notice tone="blue" icon="chat">
            Nenhuma mensagem ainda. Comece a conversa com o clã.
          </Notice>
        }
      />
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <Input
          value={draft}
          onChangeText={(value) => {
            draftRef.current = value;
            setDraft(value);
          }}
          placeholder="Mensagem para o clã"
          maxLength={2000}
          style={{ flex: 1 }}
          returnKeyType="send"
          blurOnSubmit={false}
          onSubmitEditing={send}
        />
        <IconBtn
          icon="send"
          label="Enviar mensagem"
          ink
          disabled={draft.trim().length === 0}
          onPress={send}
        />
      </View>
      <BottomSheetFrame
        visible={reportOpen}
        onClose={() => setReportOpen(false)}
        title="Denunciar mensagens"
        subtitle={`${selectedMessages.length === 1 ? '1 mensagem selecionada' : `${selectedMessages.length} mensagens selecionadas`}. A denúncia é privada; o autor não vê quem denunciou.`}
        accessibilityLabel="Denunciar mensagens"
        footer={
          <ClanReportFooter
            count={selectedMessages.length}
            busy={reporting}
            disabled={reason.trim().length === 0}
            onConfirm={() => void submitReport()}
          />
        }
      >
        <Field label="Motivo">
          <Textarea
            value={reason}
            onChangeText={(value) => {
              setReason(value);
              setReportError(null);
            }}
            maxLength={300}
            placeholder="Descreva o motivo da denúncia"
            autoFocus
          />
        </Field>
        <Txt variant="tiny">{reason.trim().length}/300</Txt>
        {reportError ? (
          <Notice tone="orange" icon="alert">
            {reportError}
          </Notice>
        ) : null}
      </BottomSheetFrame>
    </Page>
  );
}

function ClanRanking() {
  const { palette } = useTheme();
  const { session, primaryFormatId, clan } = useApp();
  const token = session?.accessToken ?? null;
  const { formats, busy: catalogBusy, failed: catalogFailed, retry } = useFormatOptions();
  const [selected, setSelected] = useState<string | null>(null);
  const [result, setResult] = useState<{
    key: string;
    status: 'ready' | 'error';
    data?: ClanRankingData;
  } | null>(null);
  const [retryTick, setRetryTick] = useState(0);
  const requestSeq = useRef(0);

  const formatId = useMemo(() => {
    if (selected && formats.some((format) => format.id === selected)) {
      return selected;
    }
    if (primaryFormatId && formats.some((format) => format.id === primaryFormatId)) {
      return primaryFormatId;
    }
    return formats[0]?.id ?? null;
  }, [formats, primaryFormatId, selected]);

  const requestKey = `${formatId ?? 'none'}|${retryTick}`;
  const status: 'idle' | 'loading' | 'ready' | 'error' = !formatId
    ? 'idle'
    : result?.key === requestKey
      ? result.status
      : 'loading';
  const data = result?.key === requestKey ? (result.data ?? null) : null;

  useEffect(() => {
    if (!token || !formatId) {
      return;
    }
    const run = ++requestSeq.current;
    api.clans
      .ranking(token, formatId)
      .then((response) => {
        if (run !== requestSeq.current) {
          return;
        }
        setResult({ key: requestKey, status: 'ready', data: response });
      })
      .catch(() => {
        if (run !== requestSeq.current) {
          return;
        }
        setResult({ key: requestKey, status: 'error' });
      });
  }, [token, formatId, requestKey]);

  const formatName =
    formats.find((format) => format.id === (data?.format_id ?? formatId))?.name ?? 'Formato';
  const list = data?.entries ?? [];

  return (
    <Page title="Ranking de clãs">
      <Field label="Esporte e formato">
        <FormatPicker
          formats={formats}
          busy={catalogBusy}
          failed={catalogFailed}
          retry={() => void retry()}
          value={formatId}
          onChange={setSelected}
        />
      </Field>
      {status === 'loading' ? (
        <LoadingState label="Carregando ranking de clãs." variant="cards" />
      ) : null}
      {status === 'error' ? (
        <StateScreen
          icon="wifi-off"
          title="Ranking indisponível"
          text="Não foi possível buscar o ranking deste formato."
          actions={
            <Btn tone="primary" onPress={() => setRetryTick((value) => value + 1)}>
              Tentar novamente
            </Btn>
          }
        />
      ) : null}
      {status === 'ready' ? (
        <>
          <Row between>
            <Txt variant="tiny">
              {formatName} · Temporada {data?.season_code ?? '—'}
            </Txt>
            <Badge>TOP 20</Badge>
          </Row>
          {list.length === 0 ? (
            <EmptyState
              title="Ranking vazio"
              text="Aparece quando os clãs tiverem partidas neste formato."
            />
          ) : (
            <CardList>
              {list.map((item, index) => (
                <ListRow key={`${item.position}-${item.clan_id}`} last={index === list.length - 1}>
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
                      {item.clan_id === clan?.id ? 'seu clã' : displayClanTag(item.tag)}
                    </Text>
                  </View>
                  <Txt variant="num" style={{ fontSize: 16 }}>
                    {number(item.trophies)}
                  </Txt>
                </ListRow>
              ))}
            </CardList>
          )}
        </>
      ) : null}
      <Notice tone="blue" icon="info">
        O ranking de clãs soma os troféus do formato escolhido na temporada.
      </Notice>
    </Page>
  );
}

function Ranking() {
  const { palette } = useTheme();
  const { session, primaryFormatId, loadRating } = useApp();
  const token = session?.accessToken ?? null;
  const { formats, busy: catalogBusy, failed: catalogFailed, retry } = useFormatOptions();
  const [selected, setSelected] = useState<string | null>(null);
  const [result, setResult] = useState<{
    key: string;
    status: 'ready' | 'error';
    entries?: { position: number; name: string; division: string; matches: number }[];
    myRating?: MyRating | null;
    ratingError?: boolean;
  } | null>(null);
  const [retryTick, setRetryTick] = useState(0);
  const requestSeq = useRef(0);

  const formatId = useMemo(() => {
    if (selected && formats.some((format) => format.id === selected)) {
      return selected;
    }
    if (primaryFormatId && formats.some((format) => format.id === primaryFormatId)) {
      return primaryFormatId;
    }
    return formats[0]?.id ?? null;
  }, [formats, primaryFormatId, selected]);

  const requestKey = `${formatId ?? 'none'}|${retryTick}`;
  const status: 'idle' | 'loading' | 'ready' | 'error' = !formatId
    ? 'idle'
    : result?.key === requestKey
      ? result.status
      : 'loading';
  const entries = result?.key === requestKey ? (result.entries ?? []) : [];
  const myRating = result?.key === requestKey ? (result.myRating ?? null) : null;
  const ratingError = result?.key === requestKey ? !!result.ratingError : false;

  useEffect(() => {
    if (!token || !formatId) {
      return;
    }
    const run = ++requestSeq.current;
    Promise.all([
      api.ratings.ranking(token, formatId, 20),
      loadRating(formatId)
        .then((value) => ({ ok: true as const, value }))
        .catch(() => ({ ok: false as const, value: null })),
    ])
      .then(([ranking, mine]) => {
        if (run !== requestSeq.current) {
          return;
        }
        setResult({
          key: requestKey,
          status: 'ready',
          entries: ranking.entries.map((item) => ({
            position: item.position,
            name: item.display_name ?? 'Jogador',
            division: divisionLabel(item.division),
            matches: item.matches_played,
          })),
          myRating: mine.value,
          ratingError: !mine.ok,
        });
      })
      .catch(() => {
        if (run !== requestSeq.current) {
          return;
        }
        setResult({ key: requestKey, status: 'error' });
      });
  }, [token, formatId, requestKey, loadRating]);

  const hasMatches = (myRating?.matches_played ?? 0) > 0;
  const formatName = formats.find((format) => format.id === formatId)?.name ?? 'Formato';

  return (
    <Page title="Ranking">
      <Field label="Esporte e formato">
        <FormatPicker
          formats={formats}
          busy={catalogBusy}
          failed={catalogFailed}
          retry={() => void retry()}
          value={formatId}
          onChange={setSelected}
        />
      </Field>
      {status === 'loading' ? <LoadingState label="Carregando ranking." variant="cards" /> : null}
      {status === 'error' ? (
        <StateScreen
          icon="wifi-off"
          title="Ranking indisponível"
          text="Não foi possível buscar o ranking deste formato."
          actions={
            <Btn tone="primary" onPress={() => setRetryTick((value) => value + 1)}>
              Tentar novamente
            </Btn>
          }
        />
      ) : null}
      {status === 'ready' ? (
        <>
          <Card tone="blue">
            <Row between>
              <Badge tone="blue">SUA POSIÇÃO</Badge>
              <Badge>{myRating?.position ? `#${myRating.position}` : '—'}</Badge>
            </Row>
            <Txt variant="h2" style={{ marginTop: 8 }}>
              {ratingError
                ? 'Posição indisponível'
                : hasMatches
                  ? myRating?.provisional
                    ? 'Provisório'
                    : myRating
                      ? divisionLabel(myRating.division)
                      : '—'
                  : 'Sem partidas neste formato'}
            </Txt>
            <Txt variant="tiny">
              {ratingError
                ? 'Não foi possível carregar sua posição neste formato.'
                : hasMatches
                  ? `${myRating?.matches_played ?? 0} partidas · ${formatName}`
                  : `Jogue uma partida ranqueada de ${formatName} para entrar no ranking.`}
            </Txt>
            {ratingError ? (
              <TextBtn onPress={() => setRetryTick((value) => value + 1)}>
                Tentar carregar minha posição
              </TextBtn>
            ) : null}
          </Card>
          {entries.length === 0 ? (
            <EmptyState
              title="Ranking vazio"
              text="Jogadores aparecem aqui depois das primeiras partidas ranqueadas neste formato."
            />
          ) : (
            <CardList>
              {entries.map((item, index) => (
                <ListRow key={item.position} last={index === entries.length - 1}>
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
          )}
        </>
      ) : null}
      <Notice tone="blue" icon="info">
        As 5 primeiras ranqueadas aparecem como “Provisório”.
      </Notice>
    </Page>
  );
}

type ClanInviteBlock = {
  text: string;
  showClan?: boolean;
  hideActions?: boolean;
  retryable?: boolean;
};

function Notifications() {
  const { palette } = useTheme();
  const nav = useNav();
  const {
    session,
    notifications,
    unreadNotifications,
    loadNotifications,
    markNotificationRead,
    markAllNotificationsRead,
    loadClan,
  } = useApp();
  const token = session?.accessToken ?? null;
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [invites, setInvites] = useState<ClanInviteData[]>([]);
  const [invitesFailed, setInvitesFailed] = useState(false);
  const [inviteBusy, setInviteBusy] = useState<string | null>(null);
  const [inviteBusyAction, setInviteBusyAction] = useState<'accept' | 'decline' | null>(null);
  const [inviteErrors, setInviteErrors] = useState<Record<string, string>>({});
  const [inviteBlocks, setInviteBlocks] = useState<Record<string, ClanInviteBlock>>({});
  const [joined, setJoined] = useState<{ id: string; clanName: string }[]>([]);
  const inviteLock = useRef<string | null>(null);
  const mounted = useRef(true);
  const actionsLocked = inviteBusy !== null;

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const loadInvites = useCallback(async () => {
    if (!token) {
      return;
    }
    try {
      const result = await api.clans.receivedInvites(token);
      if (mounted.current) {
        setInvites(result.invites);
        setInvitesFailed(false);
      }
    } catch {
      if (mounted.current) {
        setInvitesFailed(true);
      }
    }
  }, [token]);

  useEffect(() => {
    let active = true;
    const invitesRequest = token
      ? api.clans.receivedInvites(token).then((result) => result.invites)
      : Promise.resolve<ClanInviteData[]>([]);
    Promise.allSettled([loadNotifications(), invitesRequest]).then(([feed, inviteResult]) => {
      if (!active) {
        return;
      }
      if (inviteResult.status === 'fulfilled') {
        setInvites(inviteResult.value);
        setInvitesFailed(false);
      } else {
        setInvitesFailed(true);
      }
      setFailed(feed.status === 'rejected');
      setLoading(false);
    });
    return () => {
      active = false;
    };
  }, [loadNotifications, token]);

  const retry = () => {
    setLoading(true);
    setFailed(false);
    setInvitesFailed(false);
    Promise.allSettled([loadNotifications(), loadInvites()]).then(([feed]) => {
      if (!mounted.current) {
        return;
      }
      setFailed(feed.status === 'rejected');
      setLoading(false);
    });
  };

  const clearInviteState = (inviteId: string) => {
    setInviteErrors((current) => {
      const next = { ...current };
      delete next[inviteId];
      return next;
    });
    setInviteBlocks((current) => {
      const next = { ...current };
      delete next[inviteId];
      return next;
    });
  };

  const blockInvite = (inviteId: string, block: ClanInviteBlock) => {
    setInviteErrors((current) => {
      const next = { ...current };
      delete next[inviteId];
      return next;
    });
    setInviteBlocks((current) => ({ ...current, [inviteId]: block }));
  };

  const dropInvite = (inviteId: string) => {
    setInvites((current) => current.filter((item) => item.id !== inviteId));
    clearInviteState(inviteId);
  };

  const markInviteNotificationRead = (inviteId: string) => {
    const item = notifications.find(
      (notification) =>
        (notification.data?.clan_invite_id ?? notification.data?.invite_id) === inviteId &&
        !notification.read_at,
    );
    if (item) {
      markNotificationRead(item.id).catch(() => undefined);
    }
  };

  const accept = async (invite: ClanInviteData) => {
    if (!token || inviteLock.current) {
      return;
    }
    inviteLock.current = invite.id;
    setInviteBusy(invite.id);
    setInviteBusyAction('accept');
    clearInviteState(invite.id);
    try {
      const updated = await api.clans.acceptInvite(token, invite.id);
      if (!mounted.current) {
        return;
      }
      const clanName = updated.name || invite.clan_name;
      setInvites((current) => current.filter((item) => item.id !== invite.id));
      setJoined((current) => [...current, { id: invite.id, clanName }]);
      markInviteNotificationRead(invite.id);
      AccessibilityInfo.announceForAccessibility(`Você entrou no clã ${clanName}`);
      try {
        await loadClan();
      } catch {
        // O perfil do clã refaz a leitura quando aberto.
      }
      loadNotifications().catch(() => undefined);
    } catch (cause) {
      if (!mounted.current) {
        return;
      }
      const code = apiErrorCode(cause);
      if (code === 'already_in_clan') {
        blockInvite(invite.id, { text: 'Você já está em um clã.', showClan: true });
      } else if (code === 'clan_full') {
        blockInvite(invite.id, { text: 'O clã está cheio.' });
      } else if (code === 'clan_cooldown') {
        blockInvite(invite.id, {
          text: 'Você saiu de um clã há pouco. Tente novamente mais tarde.',
          retryable: true,
        });
      } else if (code === 'invite_expired') {
        blockInvite(invite.id, { text: 'Este convite expirou.', hideActions: true });
      } else if (code === 'invite_not_pending') {
        blockInvite(invite.id, {
          text: 'Este convite não está mais disponível.',
          hideActions: true,
        });
      } else if (code === 'invite_not_found' || code === 'not_found') {
        dropInvite(invite.id);
        nav.toast('Este convite não está mais disponível.');
      } else {
        setInviteErrors((current) => ({
          ...current,
          [invite.id]: 'Não foi possível aceitar. Tente de novo.',
        }));
      }
    } finally {
      inviteLock.current = null;
      if (mounted.current) {
        setInviteBusy(null);
        setInviteBusyAction(null);
      }
    }
  };

  const decline = async (invite: ClanInviteData) => {
    if (!token || inviteLock.current) {
      return;
    }
    inviteLock.current = invite.id;
    setInviteBusy(invite.id);
    setInviteBusyAction('decline');
    clearInviteState(invite.id);
    try {
      await api.clans.declineInvite(token, invite.id);
      if (!mounted.current) {
        return;
      }
      dropInvite(invite.id);
      markInviteNotificationRead(invite.id);
      AccessibilityInfo.announceForAccessibility('Convite recusado');
    } catch (cause) {
      if (!mounted.current) {
        return;
      }
      const code = apiErrorCode(cause);
      if (
        code === 'invite_expired' ||
        code === 'invite_not_pending' ||
        code === 'invite_not_found' ||
        code === 'not_found'
      ) {
        dropInvite(invite.id);
        nav.toast('Este convite não está mais disponível.');
      } else {
        setInviteErrors((current) => ({
          ...current,
          [invite.id]: 'Não foi possível recusar. Tente de novo.',
        }));
      }
    } finally {
      inviteLock.current = null;
      if (mounted.current) {
        setInviteBusy(null);
        setInviteBusyAction(null);
      }
    }
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
    // Convite de clã é tratado antes de `invite`: ele tem ação própria na
    // seção "Convites de clã" e nunca deve abrir o convite de lobby.
    if (item.kind.includes('clan')) {
      if (item.kind.includes('invite')) {
        return;
      }
      nav.go('clan');
      return;
    }
    if (item.kind.includes('invite')) {
      const inviteId =
        typeof data.invite_id === 'string'
          ? data.invite_id
          : typeof data.id === 'string'
            ? data.id
            : undefined;
      nav.go('lobby-invite-received', inviteId ? { inviteId } : undefined);
      return;
    }
    if (item.kind.includes('match') || item.kind.includes('lobby')) {
      nav.go('lobby-detail', matchId ? { matchId } : undefined);
      return;
    }
  };

  if (loading) {
    return (
      <Page title="Notificações">
        <LoadingState label="Buscando notificações." variant="list" />
      </Page>
    );
  }

  if (failed && invitesFailed) {
    return (
      <Page title="Notificações">
        <StateScreen
          icon="wifi-off"
          title="Não foi possível carregar as notificações"
          text="Verifique a conexão e tente novamente. Seu histórico continua salvo."
          actions={
            <Btn tone="primary" onPress={retry}>
              Tentar novamente
            </Btn>
          }
        />
      </Page>
    );
  }

  if (!notifications.length && !invites.length && !joined.length && !invitesFailed && !failed) {
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
        <Txt variant="h3">Convites de clã{invites.length > 0 ? ` (${invites.length})` : ''}</Txt>
        {invitesFailed ? (
          <TextBtn muted onPress={() => void loadInvites()}>
            Tentar novamente
          </TextBtn>
        ) : null}
      </Row>
      {invitesFailed ? (
        <Notice tone="orange" icon="alert">
          Não foi possível carregar os convites de clã.
        </Notice>
      ) : null}
      {!invitesFailed && invites.length === 0 && joined.length === 0 ? (
        <Card>
          <Txt variant="tiny">Nenhum convite de clã no momento.</Txt>
        </Card>
      ) : null}
      {joined.map((item) => (
        <Card key={`joined-${item.id}`}>
          <Txt variant="sub">Você entrou no clã {item.clanName}.</Txt>
          <Row style={{ marginTop: 8 }}>
            <Btn tone="primary" small block={false} onPress={() => nav.go('clan')}>
              Abrir clã
            </Btn>
          </Row>
        </Card>
      ))}
      {invites.length > 0 ? (
        <CardList>
          {invites.map((invite, index) => {
            const inviter = invite.inviter_display_name ?? 'Jogador';
            const expiry = inviteExpiryLabel(invite.expires_at);
            const blocked = inviteBlocks[invite.id];
            const rowError = inviteErrors[invite.id];
            const busy = inviteBusy === invite.id;
            return (
              <ListRow key={invite.id} last={index === invites.length - 1}>
                <IdentityBadge
                  size={34}
                  identity={identityFromSeed(invite.inviter_id)}
                  palette={palette}
                />
                <View style={{ flex: 1, gap: 6 }}>
                  <Text
                    numberOfLines={3}
                    style={{ fontSize: 14, lineHeight: 19, fontWeight: '800', color: palette.ink }}
                  >
                    {`${inviter} convidou você para o clã ${invite.clan_name}`}
                  </Text>
                  <Txt variant="tiny">{expiry ?? 'Convite válido por 7 dias.'}</Txt>
                  {blocked ? (
                    <Txt variant="tiny" color="red">
                      {blocked.text}
                    </Txt>
                  ) : null}
                  {rowError ? (
                    <Txt variant="tiny" color="red">
                      {rowError}
                    </Txt>
                  ) : null}
                  {blocked?.showClan ? (
                    <TextBtn onPress={() => nav.go('clan')}>Ver meu clã</TextBtn>
                  ) : null}
                  {!blocked || !blocked.hideActions ? (
                    <BtnRow>
                      <Btn
                        tone="primary"
                        small
                        disabled={actionsLocked || (!!blocked && !blocked.retryable)}
                        onPress={() => void accept(invite)}
                      >
                        {busy && inviteBusyAction === 'accept' ? 'Aceitando.' : 'Aceitar'}
                      </Btn>
                      <Btn
                        tone="ghost"
                        small
                        disabled={actionsLocked}
                        onPress={() => void decline(invite)}
                      >
                        {busy && inviteBusyAction === 'decline' ? 'Recusando.' : 'Recusar'}
                      </Btn>
                    </BtnRow>
                  ) : null}
                </View>
              </ListRow>
            );
          })}
        </CardList>
      ) : null}

      {failed && notifications.length === 0 ? (
        <View style={{ gap: 6 }}>
          <Notice tone="orange" icon="alert">
            Não foi possível carregar o restante das notificações.
          </Notice>
          <TextBtn onPress={retry}>Tentar novamente</TextBtn>
        </View>
      ) : null}

      {notifications.length > 0 ? (
        <>
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
          {failed ? (
            <Notice tone="orange" icon="alert">
              Algumas notificações não carregaram.
            </Notice>
          ) : null}
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
                        <Badge tone={decision === 'ACCEPTED' ? 'green' : 'red'}>
                          {decisionLabel}
                        </Badge>
                      </View>
                    ) : null}
                  </View>
                  {unread ? <Badge tone="lime">NOVA</Badge> : null}
                </ListRow>
              );
            })}
          </CardList>
        </>
      ) : null}
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
  const { session, matches, queue, matchedEntry } = useApp();
  const targetUserId = typeof nav.params.userId === 'string' ? nav.params.userId : null;
  const targetName = typeof nav.params.name === 'string' ? nav.params.name : 'Jogador';
  const lobbyId =
    (typeof nav.params.lobbyId === 'string' && nav.params.lobbyId) ||
    matches.find((match) => match.lobby_id)?.lobby_id ||
    lobbyIdFromQueue(queue, matchedEntry) ||
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
          text="Abra a denúncia pelo perfil do jogador de um lobby em comum."
          actions={
            <>
              <Btn tone="primary" go="matches">
                Ver partidas
              </Btn>
              <Btn tone="ghost" onPress={() => nav.go('queue', { mode: 'casual' })}>
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
        A denúncia é privada. O alvo não vê quem denunciou; não há punição automática.
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
          text="Verifique a conexão e tente novamente. Seu histórico continua salvo."
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
          text="Suas denúncias e medidas aparecem aqui. A triagem não é exposta."
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
          <IdentityBadge size={86} identity={identityFromSeed('Marcus_rise')} palette={palette} />
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

type PendingClanInvite = {
  id: string;
  userId: string;
  name: string;
  createdAt: string;
};

function ClanInvite() {
  const nav = useNav();
  const { palette } = useTheme();
  const { clan, clanMembers, friends, session, loadSocial } = useApp();
  const token = session?.accessToken ?? null;
  const [query, setQuery] = useState('');
  const [friendsLoading, setFriendsLoading] = useState(friends.length === 0);
  const [friendsFailed, setFriendsFailed] = useState(false);
  const [sendingIds, setSendingIds] = useState<Record<string, boolean>>({});
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});
  const [rowBlocks, setRowBlocks] = useState<Record<string, string>>({});
  const [pending, setPending] = useState<PendingClanInvite[]>([]);
  const [cancelBusy, setCancelBusy] = useState<string | null>(null);
  const [cancelErrors, setCancelErrors] = useState<Record<string, string>>({});
  const sendingRef = useRef<Set<string>>(new Set());
  const cancelLock = useRef<string | null>(null);
  const mounted = useRef(true);
  const canInvite = isAdminRole(clan?.my_role);
  const isFull = !!clan && clan.members >= clan.max_members;
  const memberIds = new Set(clanMembers.map((member) => member.user_id));
  const pendingIds = new Set(pending.map((invite) => invite.userId));
  const nameOf = (friend: { display_name: string | null }) =>
    friend.display_name?.trim() || 'Jogador';

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    if (friends.length > 0) {
      return;
    }
    let active = true;
    loadSocial()
      .then(() => {
        if (active) {
          setFriendsLoading(false);
        }
      })
      .catch(() => {
        if (active) {
          setFriendsLoading(false);
          setFriendsFailed(true);
        }
      });
    return () => {
      active = false;
    };
  }, [loadSocial, friends.length]);

  const clearRow = (userId: string) => {
    setRowErrors((current) => {
      const next = { ...current };
      delete next[userId];
      return next;
    });
    setRowBlocks((current) => {
      const next = { ...current };
      delete next[userId];
      return next;
    });
  };

  const send = async (friend: { user_id: string; display_name: string | null }) => {
    if (!clan || !token || isFull) {
      return;
    }
    if (
      memberIds.has(friend.user_id) ||
      pendingIds.has(friend.user_id) ||
      sendingRef.current.has(friend.user_id)
    ) {
      return;
    }
    sendingRef.current.add(friend.user_id);
    setSendingIds((current) => ({ ...current, [friend.user_id]: true }));
    clearRow(friend.user_id);
    try {
      const created = await api.clans.invite(token, clan.id, friend.user_id);
      if (!mounted.current) {
        return;
      }
      setPending((current) => [
        {
          id: created.id,
          userId: friend.user_id,
          name: nameOf(friend),
          createdAt: created.created_at,
        },
        ...current.filter((item) => item.userId !== friend.user_id),
      ]);
      AccessibilityInfo.announceForAccessibility('Convite enviado');
    } catch (cause) {
      if (!mounted.current) {
        return;
      }
      const code = apiErrorCode(cause);
      const block =
        code === 'not_friends'
          ? 'Só é possível convidar amigos.'
          : code === 'blocked'
            ? 'Não é possível convidar esta pessoa.'
            : code === 'already_invited'
              ? 'Este convite já foi enviado.'
              : code === 'already_member'
                ? 'Essa pessoa já está no clã.'
                : code === 'clan_full'
                  ? 'O clã está cheio.'
                  : code === 'cannot_invite_self'
                    ? 'Você não pode convidar a si mesmo.'
                    : null;
      if (block) {
        setRowBlocks((current) => ({ ...current, [friend.user_id]: block }));
      } else {
        setRowErrors((current) => ({
          ...current,
          [friend.user_id]: 'Não foi possível enviar. Tente de novo.',
        }));
      }
    } finally {
      sendingRef.current.delete(friend.user_id);
      if (mounted.current) {
        setSendingIds((current) => {
          const next = { ...current };
          delete next[friend.user_id];
          return next;
        });
      }
    }
  };

  const cancel = async (invite: PendingClanInvite) => {
    if (!clan || !token || cancelLock.current) {
      return;
    }
    cancelLock.current = invite.id;
    setCancelBusy(invite.id);
    setCancelErrors((current) => {
      const next = { ...current };
      delete next[invite.id];
      return next;
    });
    try {
      await api.clans.cancelInvite(token, clan.id, invite.id);
      if (!mounted.current) {
        return;
      }
      setPending((current) => current.filter((item) => item.id !== invite.id));
      AccessibilityInfo.announceForAccessibility('Convite cancelado');
    } catch (cause) {
      if (!mounted.current) {
        return;
      }
      const code = apiErrorCode(cause);
      if (
        code === 'not_found' ||
        code === 'invite_not_found' ||
        code === 'invite_not_pending' ||
        code === 'invite_expired'
      ) {
        setPending((current) => current.filter((item) => item.id !== invite.id));
      } else {
        setCancelErrors((current) => ({
          ...current,
          [invite.id]: 'Não foi possível cancelar. Tente de novo.',
        }));
      }
    } finally {
      cancelLock.current = null;
      if (mounted.current) {
        setCancelBusy(null);
      }
    }
  };

  if (!clan) {
    return (
      <Page title="Convidar membros">
        <EmptyState
          title="Você não está em um clã"
          text="Entre em um clã para convidar seus amigos."
          actions={
            <Btn tone="primary" go="clan-discovery">
              Descobrir clãs
            </Btn>
          }
        />
      </Page>
    );
  }

  if (!canInvite) {
    return (
      <Page title="Convidar membros">
        <StateScreen
          icon="shield"
          title="Sem permissão para convidar"
          text="Só o Dono e os Oficiais podem convidar."
          actions={
            <Btn tone="ghost" back>
              Voltar
            </Btn>
          }
        />
      </Page>
    );
  }

  const matching = friends.filter((friend) => matchesSearch(nameOf(friend), query));

  return (
    <Page title="Convidar membros" sub={clan.name}>
      {isFull ? (
        <Notice tone="orange" icon="alert">
          Seu clã está cheio. Libere uma vaga para convidar.
        </Notice>
      ) : null}
      <Field label="Buscar amigo">
        <Input
          value={query}
          onChangeText={setQuery}
          placeholder="Nome do amigo"
          maxLength={60}
          autoCorrect={false}
          autoCapitalize="none"
          accessibilityLabel="Buscar amigo para convidar"
        />
      </Field>
      {query.trim().length > 0 ? (
        <TextBtn muted onPress={() => setQuery('')}>
          Limpar busca
        </TextBtn>
      ) : null}

      {friendsLoading && friends.length === 0 ? (
        <LoadingState label="Buscando seus amigos." variant="list" />
      ) : friendsFailed && friends.length === 0 ? (
        <StateScreen
          icon="wifi-off"
          title="Não foi possível carregar seus amigos"
          text="Verifique a conexão e tente novamente."
          actions={
            <Btn
              tone="primary"
              onPress={() => {
                setFriendsFailed(false);
                setFriendsLoading(true);
                loadSocial()
                  .then(() => setFriendsLoading(false))
                  .catch(() => {
                    setFriendsLoading(false);
                    setFriendsFailed(true);
                  });
              }}
            >
              Tentar novamente
            </Btn>
          }
        />
      ) : friends.length === 0 ? (
        <EmptyState
          title="Você ainda não tem amigos para convidar"
          text="Adicione amigos para trazer mais gente para o clã."
          actions={
            <Btn tone="primary" go="friends">
              Ver amigos
            </Btn>
          }
        />
      ) : matching.length === 0 ? (
        <EmptyState
          title="Nenhum amigo com esse nome"
          text="Confira a grafia ou limpe a busca."
          actions={
            <Btn tone="ghost" onPress={() => setQuery('')}>
              Limpar busca
            </Btn>
          }
        />
      ) : (
        <CardList>
          {matching.map((friend, index) => {
            const name = nameOf(friend);
            const isMember = memberIds.has(friend.user_id);
            const isPending = pendingIds.has(friend.user_id);
            const block = rowBlocks[friend.user_id];
            const rowError = rowErrors[friend.user_id];
            const sending = !!sendingIds[friend.user_id];
            const subtitle = isMember
              ? 'Já está no clã'
              : isPending
                ? 'Convite pendente'
                : isFull
                  ? 'Sem vaga no clã'
                  : 'Amigo';
            return (
              <ListRow key={friend.user_id} last={index === matching.length - 1}>
                <IdentityBadge
                  size={34}
                  identity={identityFromSeed(friend.user_id)}
                  palette={palette}
                />
                <View style={{ flex: 1, gap: 6 }}>
                  <Text
                    numberOfLines={2}
                    style={{ fontSize: 14, lineHeight: 18, fontWeight: '800', color: palette.ink }}
                  >
                    {name}
                  </Text>
                  <Text style={{ fontSize: 13, lineHeight: 18, color: palette.muted }}>
                    {block ?? subtitle}
                  </Text>
                  {rowError ? (
                    <Txt variant="tiny" color="red">
                      {rowError}
                    </Txt>
                  ) : null}
                </View>
                {!isMember && !isPending && !block ? (
                  <Btn
                    tone="primary"
                    small
                    block={false}
                    disabled={isFull || sending}
                    onPress={() => void send(friend)}
                  >
                    {sending ? 'Enviando.' : rowError ? 'Tentar de novo' : 'Convidar'}
                  </Btn>
                ) : null}
              </ListRow>
            );
          })}
        </CardList>
      )}

      {pending.length > 0 ? (
        <>
          <Txt variant="h3">Convites pendentes</Txt>
          <CardList>
            {pending.map((invite, index) => {
              const busy = cancelBusy === invite.id;
              const cancelError = cancelErrors[invite.id];
              return (
                <ListRow key={invite.id} last={index === pending.length - 1}>
                  <View style={{ flex: 1, gap: 4 }}>
                    <Text
                      numberOfLines={2}
                      style={{
                        fontSize: 14,
                        lineHeight: 18,
                        fontWeight: '800',
                        color: palette.ink,
                      }}
                    >
                      {invite.name}
                    </Text>
                    <Txt variant="tiny">{`${shortDateTime(invite.createdAt)} · vale por 7 dias`}</Txt>
                    {cancelError ? (
                      <Txt variant="tiny" color="red">
                        {cancelError}
                      </Txt>
                    ) : null}
                  </View>
                  <Btn
                    tone="ghost"
                    small
                    block={false}
                    disabled={busy}
                    onPress={() => void cancel(invite)}
                  >
                    {busy ? 'Cancelando.' : 'Cancelar'}
                  </Btn>
                </ListRow>
              );
            })}
          </CardList>
        </>
      ) : null}

      <Notice tone="blue" icon="info">
        Só amigos podem ser convidados. O convite vale por 7 dias.
      </Notice>
      <TextBtn muted onPress={() => nav.back()}>
        Voltar
      </TextBtn>
    </Page>
  );
}

function ClanFull() {
  return (
    <Page title="Clã cheio">
      <StateScreen
        icon="users"
        title="Este clã está cheio"
        text="Sem vagas agora. Escolha outro clã ou volte depois."
        actions={
          <>
            <Btn tone="primary" go="clan-discovery">
              Ver outros clãs
            </Btn>
            <Btn tone="ghost" back>
              Voltar
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
  { id: 'block-user', tab: 'social', hidden: true, render: () => <BlockUser /> },
  { id: 'clan-invite', tab: 'social', render: () => <ClanInvite /> },
  { id: 'clan-full', tab: 'social', render: () => <ClanFull /> },
];
