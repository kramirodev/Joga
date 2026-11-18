import { useEffect, useState } from 'react';
import * as Clipboard from 'expo-clipboard';
import { Image, Linking, View } from 'react-native';

import type { BookingPayment, PurchasePayment } from '../api/types';
import { useNav } from '../state/context';
import { cents } from './datetime';
import { Badge, Btn, Card, Notice, Row, TimerCard, Txt } from './kit';

export function paymentState(
  ...statuses: (string | null | undefined)[]
): 'pending' | 'paid' | 'expired' | 'failed' {
  const values = statuses
    .filter((item): item is string => typeof item === 'string' && item.length > 0)
    .map((item) => item.toUpperCase());
  if (
    values.some((value) => ['PAID', 'PROCESSED', 'APPROVED', 'ACTIVE', 'CONFIRMED'].includes(value))
  ) {
    return 'paid';
  }
  if (values.some((value) => ['EXPIRED', 'CANCELLED', 'CANCELED'].includes(value))) {
    return 'expired';
  }
  if (values.some((value) => ['FAILED', 'REJECTED', 'REFUNDED'].includes(value))) {
    return 'failed';
  }
  return 'pending';
}

export function paymentStateLabel(state: 'pending' | 'paid' | 'expired' | 'failed'): string {
  if (state === 'paid') return 'PAGO';
  if (state === 'expired') return 'EXPIRADO';
  if (state === 'failed') return 'NÃO CONCLUÍDO';
  return 'AGUARDANDO PAGAMENTO';
}

function usePaymentCountdown(expiresAt: string | null) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  if (!expiresAt) {
    return null;
  }
  const remaining = new Date(expiresAt).getTime() - now;
  const safe = Math.max(0, remaining);
  const minutes = Math.floor(safe / 60000);
  const seconds = Math.floor((safe % 60000) / 1000);
  return {
    expired: remaining <= 0,
    label: `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`,
  };
}

export function PaymentPix({
  payment,
  purchaseStatus,
  amountCents,
  onRefresh,
  refreshing,
}: {
  payment: PurchasePayment | BookingPayment | null;
  purchaseStatus?: string | null;
  amountCents?: number | null;
  onRefresh: () => void;
  refreshing?: boolean;
}) {
  const nav = useNav();
  const countdown = usePaymentCountdown(payment?.expires_at ?? null);
  const state = paymentState(purchaseStatus, payment?.provider_status);
  const qrCode = payment?.qr_code ?? null;

  const copy = async () => {
    if (!qrCode) {
      nav.toast('Código Pix indisponível.');
      return;
    }
    await Clipboard.setStringAsync(qrCode);
    nav.toast('Código Pix copiado.');
  };

  return (
    <Card style={{ alignItems: 'center' }}>
      {payment?.qr_code_base64 && payment.qr_code_base64.length > 100 ? (
        <Image
          source={{ uri: `data:image/png;base64,${payment.qr_code_base64}` }}
          style={{ width: 188, height: 188 }}
          resizeMode="contain"
        />
      ) : (
        <Notice tone="orange" icon="alert">
          O QR ainda não está disponível. Atualize o status ou tente novamente em instantes.
        </Notice>
      )}
      {qrCode ? (
        <View style={{ width: '100%', marginTop: 10 }}>
          <Btn tone="ghost" icon="copy" onPress={copy}>
            Copiar código Pix
          </Btn>
        </View>
      ) : null}
      {payment?.ticket_url ? (
        <View style={{ width: '100%', marginTop: 8 }}>
          <Btn tone="ghost" icon="wallet" onPress={() => Linking.openURL(payment.ticket_url!)}>
            Abrir comprovante do Mercado Pago
          </Btn>
        </View>
      ) : null}
      <Row between style={{ width: '100%', marginTop: 12 }}>
        <Badge tone={state === 'paid' ? 'green' : state === 'pending' ? 'orange' : 'red'}>
          {paymentStateLabel(state)}
        </Badge>
        {amountCents != null ? <Txt variant="num">{cents(amountCents)}</Txt> : null}
      </Row>
      {payment?.status_detail ? (
        <Txt variant="tiny" style={{ marginTop: 8 }}>
          {payment.status_detail}
        </Txt>
      ) : null}
      {payment?.external_reference ? (
        <Txt variant="tiny" style={{ marginTop: 4 }}>
          Pedido: {payment.external_reference}
        </Txt>
      ) : null}
      {countdown ? (
        <TimerCard
          label="Expiração do Pix"
          value={countdown.expired ? 'expirado' : countdown.label}
          note={countdown.expired ? 'gere uma nova cobrança' : 'pagamento pendente'}
          tone={countdown.expired ? 'done' : 'on'}
        />
      ) : null}
      <View style={{ width: '100%', marginTop: 10 }}>
        <Btn tone="primary" onPress={onRefresh} disabled={refreshing || state !== 'pending'}>
          {refreshing ? 'Verificando…' : 'Atualizar status'}
        </Btn>
      </View>
    </Card>
  );
}
