import { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import {
  ApiError,
  chatApi,
  matchesApi,
  socialApi,
  type ChatMessage,
  type Friend,
  type LobbyInvite,
  type MatchSummary,
} from './api';
import { loadSession, type StoredSession } from './session';

function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    return `${error.code} (HTTP ${error.status})`;
  }
  if (error instanceof Error && error.message.length > 0) {
    return error.message;
  }
  return 'Falha inesperada.';
}

function formatMoment(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function CommunicationPanel() {
  const [session, setSession] = useState<StoredSession | null>(null);
  const [matches, setMatches] = useState<MatchSummary[]>([]);
  const [selected, setSelected] = useState<MatchSummary | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [friends, setFriends] = useState<Friend[]>([]);
  const [invites, setInvites] = useState<LobbyInvite[]>([]);
  const [draft, setDraft] = useState('');
  const [message, setMessage] = useState('Entre na conta para usar o chat e os convites.');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    void (async () => {
      const stored = await loadSession();
      if (!stored) {
        return;
      }
      try {
        const [matchPage, friendPage, invitePage] = await Promise.all([
          matchesApi.list(stored.accessToken),
          socialApi.friends(stored.accessToken),
          socialApi.invites(stored.accessToken),
        ]);
        if (!active) {
          return;
        }
        setSession(stored);
        setMatches(matchPage.matches);
        setFriends(friendPage.friends);
        setInvites(invitePage.invites);
        if (matchPage.matches[0]) {
          await selectMatch(stored, matchPage.matches[0]);
        }
        setMessage('Comunicação carregada.');
      } catch (error) {
        if (active) {
          setMessage(describeError(error));
        }
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  async function selectMatch(stored: StoredSession, match: MatchSummary) {
    setBusy(true);
    try {
      const [detail, chat] = await Promise.all([
        matchesApi.get(stored.accessToken, match.id),
        chatApi.list(stored.accessToken, match.lobby_id),
      ]);
      setSelected(detail);
      setMessages(chat.messages);
    } catch (error) {
      setMessage(describeError(error));
    } finally {
      setBusy(false);
    }
  }

  async function chooseMatch(match: MatchSummary) {
    if (!session) {
      return;
    }
    await selectMatch(session, match);
  }

  async function sendMessage() {
    if (!session || !selected || !draft.trim()) {
      return;
    }
    setBusy(true);
    try {
      await chatApi.send(
        session.accessToken,
        selected.lobby_id,
        draft.trim(),
        `mobile-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      );
      setDraft('');
      const chat = await chatApi.list(session.accessToken, selected.lobby_id);
      setMessages(chat.messages);
      setMessage('Mensagem enviada.');
    } catch (error) {
      setMessage(describeError(error));
    } finally {
      setBusy(false);
    }
  }

  async function refresh() {
    if (!session) {
      return;
    }
    setBusy(true);
    try {
      const [matchPage, friendPage, invitePage] = await Promise.all([
        matchesApi.list(session.accessToken),
        socialApi.friends(session.accessToken),
        socialApi.invites(session.accessToken),
      ]);
      setMatches(matchPage.matches);
      setFriends(friendPage.friends);
      setInvites(invitePage.invites);
      if (selected) {
        await selectMatch(session, selected);
      }
      setMessage('Comunicação atualizada.');
    } catch (error) {
      setMessage(describeError(error));
    } finally {
      setBusy(false);
    }
  }

  async function addFriend(userId: string) {
    if (!session) {
      return;
    }
    setBusy(true);
    try {
      await socialApi.requestFriend(session.accessToken, userId);
      setMessage('Solicitação de amizade enviada.');
    } catch (error) {
      setMessage(describeError(error));
    } finally {
      setBusy(false);
    }
  }

  async function invite(friendId: string) {
    if (!session || !selected) {
      return;
    }
    setBusy(true);
    try {
      await socialApi.inviteToLobby(session.accessToken, selected.lobby_id, friendId);
      setMessage('Convite enviado.');
    } catch (error) {
      setMessage(describeError(error));
    } finally {
      setBusy(false);
    }
  }

  async function respondInvite(inviteId: string, accept: boolean) {
    if (!session) {
      return;
    }
    setBusy(true);
    try {
      if (accept) {
        await socialApi.acceptInvite(session.accessToken, inviteId);
      } else {
        await socialApi.declineInvite(session.accessToken, inviteId);
      }
      await refresh();
      setMessage(accept ? 'Convite aceito.' : 'Convite recusado.');
    } catch (error) {
      setMessage(describeError(error));
    } finally {
      setBusy(false);
    }
  }

  const participantNames = new Map(
    (selected?.participants ?? []).map((participant) => [
      participant.user_id,
      participant.display_name ?? 'Jogador',
    ]),
  );
  const friendIds = new Set(friends.map((friend) => friend.user_id));
  const participants = (selected?.participants ?? []).filter(
    (participant) => participant.user_id !== session?.userId && !friendIds.has(participant.user_id),
  );

  return (
    <View style={styles.section}>
      <Text style={styles.eyebrow}>FASE 9 • COMUNICAÇÃO</Text>
      <Text style={styles.heading}>Chat, amigos e convites</Text>
      <Text style={styles.body}>
        Mensagens são salvas no servidor antes da entrega. Atualize para reconciliar após
        reconectar.
      </Text>

      <View style={styles.chips}>
        {matches.slice(0, 5).map((match) => {
          const active = match.id === selected?.id;
          return (
            <Pressable
              accessibilityRole="button"
              accessibilityState={{ selected: active }}
              key={match.id}
              onPress={() => void chooseMatch(match)}
              style={[styles.chip, active && styles.chipSelected]}
            >
              <Text style={[styles.chipText, active && styles.chipTextSelected]}>
                {formatMoment(match.scheduled_start_at)} • {match.state}
              </Text>
            </Pressable>
          );
        })}
      </View>

      <View style={styles.card}>
        <Text style={styles.label}>Chat do lobby</Text>
        {messages.length === 0 ? (
          <Text style={styles.value}>Nenhuma mensagem ainda.</Text>
        ) : (
          messages.slice(-20).map((item) => (
            <View key={item.id} style={styles.messageRow}>
              <Text style={styles.messageAuthor}>
                {participantNames.get(item.sender_id) ?? 'Participante'}
              </Text>
              <Text style={styles.messageBody}>{item.body}</Text>
            </View>
          ))
        )}
        <TextInput
          multiline
          onChangeText={setDraft}
          placeholder="Escreva uma mensagem"
          style={styles.input}
          value={draft}
        />
        <Pressable
          accessibilityRole="button"
          disabled={busy || !selected || draft.trim().length === 0}
          onPress={() => void sendMessage()}
          style={({ pressed }) => [
            styles.button,
            pressed && styles.buttonPressed,
            (busy || !selected || draft.trim().length === 0) && styles.buttonDisabled,
          ]}
        >
          <Text style={styles.buttonText}>Enviar mensagem</Text>
        </Pressable>
      </View>

      <View style={styles.card}>
        <Text style={styles.label}>Amigos</Text>
        {friends.length === 0 ? (
          <Text style={styles.value}>Nenhum amigo ainda.</Text>
        ) : (
          friends.map((friend) => (
            <View key={friend.user_id} style={styles.row}>
              <Text style={styles.rowText}>{friend.display_name ?? 'Jogador'}</Text>
              <Pressable
                accessibilityRole="button"
                disabled={busy || !selected}
                onPress={() => void invite(friend.user_id)}
                style={styles.smallButton}
              >
                <Text style={styles.smallButtonText}>Convidar</Text>
              </Pressable>
            </View>
          ))
        )}
      </View>

      {participants.length > 0 ? (
        <View style={styles.card}>
          <Text style={styles.label}>Participantes da partida</Text>
          {participants.slice(0, 10).map((participant) => (
            <View key={participant.user_id} style={styles.row}>
              <Text style={styles.rowText}>{participant.display_name ?? 'Jogador'}</Text>
              <Pressable
                accessibilityRole="button"
                disabled={busy}
                onPress={() => void addFriend(participant.user_id)}
                style={styles.smallButton}
              >
                <Text style={styles.smallButtonText}>Adicionar</Text>
              </Pressable>
            </View>
          ))}
        </View>
      ) : null}

      <View style={styles.card}>
        <Text style={styles.label}>Convites pendentes</Text>
        {invites.length === 0 ? (
          <Text style={styles.value}>Nenhum convite pendente.</Text>
        ) : (
          invites.map((invite) => (
            <View key={invite.id} style={styles.row}>
              <Text style={styles.rowText}>Lobby {invite.lobby_id.slice(0, 8)}</Text>
              <View style={styles.rowActions}>
                <Pressable
                  accessibilityRole="button"
                  disabled={busy}
                  onPress={() => void respondInvite(invite.id, true)}
                  style={styles.smallButton}
                >
                  <Text style={styles.smallButtonText}>Aceitar</Text>
                </Pressable>
                <Pressable
                  accessibilityRole="button"
                  disabled={busy}
                  onPress={() => void respondInvite(invite.id, false)}
                  style={styles.secondarySmallButton}
                >
                  <Text style={styles.secondarySmallText}>Recusar</Text>
                </Pressable>
              </View>
            </View>
          ))
        )}
      </View>

      <Pressable
        accessibilityRole="button"
        disabled={busy}
        onPress={() => void refresh()}
        style={({ pressed }) => [
          styles.secondaryButton,
          pressed && styles.buttonPressed,
          busy && styles.buttonDisabled,
        ]}
      >
        {busy ? (
          <ActivityIndicator color="#26724a" />
        ) : (
          <Text style={styles.secondaryButtonText}>Atualizar comunicação</Text>
        )}
      </Pressable>

      <Text accessibilityLiveRegion="polite" style={styles.message}>
        {message}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  section: { gap: 12 },
  eyebrow: { color: '#26724a', fontSize: 12, fontWeight: '700', letterSpacing: 1.2 },
  heading: { color: '#173b2a', fontSize: 21, fontWeight: '700' },
  body: { color: '#52625a', fontSize: 15, lineHeight: 22 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: {
    borderColor: '#b8cdc0',
    borderRadius: 999,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  chipSelected: { backgroundColor: '#26724a', borderColor: '#26724a' },
  chipText: { color: '#26724a', fontSize: 13, fontWeight: '600' },
  chipTextSelected: { color: '#fff' },
  card: { backgroundColor: '#fff', borderRadius: 14, padding: 16, gap: 8 },
  label: { color: '#52625a', fontSize: 12, fontWeight: '700', textTransform: 'uppercase' },
  value: { color: '#173b2a', fontSize: 15, lineHeight: 22 },
  messageRow: { borderTopColor: '#e4ece7', borderTopWidth: 1, paddingTop: 8, gap: 2 },
  messageAuthor: { color: '#26724a', fontSize: 12, fontWeight: '700' },
  messageBody: { color: '#173b2a', fontSize: 15, lineHeight: 21 },
  input: {
    borderColor: '#b8cdc0',
    borderRadius: 10,
    borderWidth: 1,
    color: '#173b2a',
    minHeight: 44,
    padding: 10,
    textAlignVertical: 'top',
  },
  row: {
    alignItems: 'center',
    borderTopColor: '#e4ece7',
    borderTopWidth: 1,
    flexDirection: 'row',
    gap: 8,
    justifyContent: 'space-between',
    paddingTop: 8,
  },
  rowText: { color: '#173b2a', flex: 1, fontSize: 14 },
  rowActions: { flexDirection: 'row', gap: 6 },
  smallButton: {
    backgroundColor: '#26724a',
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 7,
  },
  smallButtonText: { color: '#fff', fontSize: 12, fontWeight: '700' },
  secondarySmallButton: {
    borderColor: '#26724a',
    borderRadius: 8,
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 7,
  },
  secondarySmallText: { color: '#26724a', fontSize: 12, fontWeight: '700' },
  button: {
    alignItems: 'center',
    backgroundColor: '#26724a',
    borderRadius: 12,
    justifyContent: 'center',
    minHeight: 48,
    padding: 14,
  },
  buttonPressed: { opacity: 0.82 },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { color: '#fff', fontSize: 15, fontWeight: '700' },
  secondaryButton: {
    alignItems: 'center',
    borderColor: '#26724a',
    borderRadius: 12,
    borderWidth: 1,
    justifyContent: 'center',
    minHeight: 48,
    padding: 14,
  },
  secondaryButtonText: { color: '#26724a', fontSize: 15, fontWeight: '700' },
  message: { color: '#52625a', fontSize: 13, lineHeight: 20 },
});
