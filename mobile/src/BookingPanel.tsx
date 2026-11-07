import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

import { ApiError, bookingsApi, type Booking } from './api';
import { loadSession, type StoredSession } from './session';

const STATUS_LABELS: Record<string, string> = {
  PARTICIPANT_CONFIRMATION: 'Confirmação dos jogadores (T1)',
  REQUESTED: 'Aguardando o estabelecimento (T2)',
  DECLINED: 'Recusada pelo estabelecimento',
  EXPIRED: 'Expirada',
  HOLD_CONFIRMED: 'Bloqueio confirmado',
  PAYMENT_PENDING: 'Aguardando pagamentos (T3)',
  CONFIRMED: 'Reserva confirmada',
  CANCELLED: 'Cancelada',
  CANCELLED_BY_VENUE: 'Cancelada pelo estabelecimento',
  CANCELLED_BY_PLAYER: 'Cancelada pelo jogador',
  SUBSTITUTING: 'Em substituição',
  COMPLETED: 'Concluída',
};

function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    return `${error.code} (HTTP ${error.status})`;
  }
  if (error instanceof Error && error.message.length > 0) {
    return error.message;
  }
  return 'Falha inesperada.';
}

function formatMoment(value: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatMoney(cents: number): string {
  return (cents / 100).toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  });
}

export function BookingPanel() {
  const [session, setSession] = useState<StoredSession | null>(null);
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [message, setMessage] = useState('Entre na conta para ver suas reservas.');
  const [busy, setBusy] = useState<string | null>(null);

  const refresh = useCallback(async (current: StoredSession | null) => {
    if (!current) {
      setBookings([]);
      setMessage('Entre na conta para ver suas reservas.');
      return;
    }
    try {
      const response = await bookingsApi.list(current.accessToken);
      setBookings(response.bookings);
      setMessage(
        response.bookings.length === 0
          ? 'Nenhuma reserva ainda. A reserva nasce quando um lobby privado é formado.'
          : 'Reservas atualizadas.',
      );
    } catch (error) {
      setMessage(describeError(error));
    }
  }, []);

  useEffect(() => {
    let active = true;
    void (async () => {
      const current = await loadSession();
      if (!active) return;
      setSession(current);
      await refresh(current);
    })();
    return () => {
      active = false;
    };
  }, [refresh]);

  async function runAction(bookingId: string, action: () => Promise<Booking>) {
    if (!session) return;
    setBusy(bookingId);
    try {
      await action();
      await refresh(session);
    } catch (error) {
      setMessage(describeError(error));
    } finally {
      setBusy(null);
    }
  }

  return (
    <View style={styles.section}>
      <Text style={styles.heading}>Reservas</Text>
      <Text style={styles.body}>
        T1 confirma a participação, T2 é a resposta do estabelecimento e T3 é o prazo de pagamento.
        Os prazos são controlados pelo servidor.
      </Text>

      <View style={styles.card}>
        <Text style={styles.label}>Estado</Text>
        <Text accessibilityLiveRegion="polite" style={styles.value}>
          {message}
        </Text>
        <Pressable
          accessibilityRole="button"
          disabled={busy !== null}
          onPress={() => void refresh(session)}
          style={({ pressed }) => [
            styles.secondaryButton,
            pressed && styles.buttonPressed,
            busy !== null && styles.buttonDisabled,
          ]}
        >
          <Text style={styles.secondaryButtonText}>Atualizar reservas</Text>
        </Pressable>
      </View>

      {bookings.map((booking) => {
        const own = booking.participants.find(
          (participant) => participant.user_id === session?.userId && participant.active,
        );
        const canConfirm =
          booking.status === 'PARTICIPANT_CONFIRMATION' &&
          own !== undefined &&
          own.confirmed_at === null &&
          own.declined_at === null;
        const canPay = booking.status === 'PAYMENT_PENDING' && own?.payment_status === 'PENDING';
        return (
          <View key={booking.id} style={styles.card}>
            <Text style={styles.label}>{STATUS_LABELS[booking.status] ?? booking.status}</Text>
            <Text style={styles.value}>
              {formatMoment(booking.starts_at)} — {formatMoment(booking.ends_at)}
            </Text>
            <Text style={styles.meta}>
              {booking.seats} vagas · {formatMoney(booking.price_cents)}
            </Text>
            <Text style={styles.meta}>
              {booking.timers
                .map(
                  (timer) =>
                    `${timer.timer_type} ${timer.status} até ${formatMoment(timer.deadline_at)}`,
                )
                .join(' · ')}
            </Text>
            {own ? (
              <Text style={styles.meta}>
                Sua vaga {own.seat} · contribuição {formatMoney(own.contribution_cents)} · pagamento{' '}
                {own.payment_status}
              </Text>
            ) : null}
            {booking.cancellation_reason ? (
              <Text style={styles.meta}>Motivo: {booking.cancellation_reason}</Text>
            ) : null}

            {canConfirm ? (
              <View style={styles.actions}>
                <Pressable
                  accessibilityRole="button"
                  disabled={busy !== null}
                  onPress={() =>
                    void runAction(booking.id, () =>
                      bookingsApi.confirm(session!.accessToken, booking.id, 'CONFIRM'),
                    )
                  }
                  style={({ pressed }) => [
                    styles.button,
                    pressed && styles.buttonPressed,
                    busy !== null && styles.buttonDisabled,
                  ]}
                >
                  {busy === booking.id ? (
                    <ActivityIndicator color="#fff" />
                  ) : (
                    <Text style={styles.buttonText}>Confirmar participação</Text>
                  )}
                </Pressable>
                <Pressable
                  accessibilityRole="button"
                  disabled={busy !== null}
                  onPress={() =>
                    void runAction(booking.id, () =>
                      bookingsApi.confirm(session!.accessToken, booking.id, 'DECLINE'),
                    )
                  }
                  style={({ pressed }) => [
                    styles.dangerButton,
                    pressed && styles.buttonPressed,
                    busy !== null && styles.buttonDisabled,
                  ]}
                >
                  <Text style={styles.dangerButtonText}>Recusar</Text>
                </Pressable>
              </View>
            ) : null}

            {canPay ? (
              <Pressable
                accessibilityRole="button"
                disabled={busy !== null}
                onPress={() =>
                  void runAction(booking.id, async () => {
                    const updated = await bookingsApi.simulatePayment(
                      session!.accessToken,
                      booking.id,
                    );
                    setMessage('Pagamento simulado apenas em ambiente local/teste.');
                    return updated;
                  })
                }
                style={({ pressed }) => [
                  styles.button,
                  pressed && styles.buttonPressed,
                  busy !== null && styles.buttonDisabled,
                ]}
              >
                {busy === booking.id ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <Text style={styles.buttonText}>Pagar (simulado local)</Text>
                )}
              </Pressable>
            ) : null}
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  section: { gap: 10 },
  heading: { color: '#173b2a', fontSize: 21, fontWeight: '700' },
  body: { color: '#52625a', fontSize: 15, lineHeight: 22 },
  card: { backgroundColor: '#fff', borderRadius: 14, padding: 16, gap: 8 },
  label: { color: '#52625a', fontSize: 12, fontWeight: '700', textTransform: 'uppercase' },
  value: { color: '#173b2a', fontSize: 15, lineHeight: 22 },
  meta: { color: '#52625a', fontSize: 13, lineHeight: 19 },
  actions: { gap: 8 },
  button: {
    alignItems: 'center',
    backgroundColor: '#26724a',
    borderRadius: 12,
    minHeight: 50,
    justifyContent: 'center',
    padding: 14,
  },
  buttonPressed: { opacity: 0.82 },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { color: '#fff', fontSize: 15, fontWeight: '700', textAlign: 'center' },
  secondaryButton: {
    alignItems: 'center',
    borderColor: '#26724a',
    borderRadius: 12,
    borderWidth: 1,
    minHeight: 46,
    justifyContent: 'center',
    padding: 12,
  },
  secondaryButtonText: { color: '#26724a', fontSize: 14, fontWeight: '700' },
  dangerButton: {
    alignItems: 'center',
    borderColor: '#a33a2b',
    borderRadius: 12,
    borderWidth: 1,
    minHeight: 46,
    justifyContent: 'center',
    padding: 12,
  },
  dangerButtonText: { color: '#a33a2b', fontSize: 14, fontWeight: '700' },
});
