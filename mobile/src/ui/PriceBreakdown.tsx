import { View } from 'react-native';

import { useTheme } from '../state/context';
import { cents } from './datetime';
import { Card, Notice, Row, Txt } from './kit';
import {
  BAND_LABELS,
  BAND_ORDER,
  BAND_RANGES,
  TICKETS_BY_BAND,
  type FormatFamily,
} from './tickets';

/**
 * Preço em duas linhas congelado pelo servidor. O app só formata os valores;
 * nenhuma taxa é calculada aqui.
 */
export function PriceBreakdown({
  venueCents,
  jogaCents,
  totalCents,
  tickets,
  fundingSource,
  feeLabel,
}: {
  venueCents: number;
  jogaCents: number;
  totalCents: number;
  tickets?: number | null;
  fundingSource?: string | null;
  feeLabel?: string;
}) {
  const { palette } = useTheme();
  const courtesy =
    fundingSource === 'pass' || fundingSource === 'free_level' || fundingSource === 'admin';
  return (
    <Card>
      <Row between>
        <Txt variant="tiny">Valor da quadra</Txt>
        <Txt variant="num" style={{ fontSize: 17 }}>
          {cents(venueCents)}
        </Txt>
      </Row>
      {!courtesy ? (
        <>
          <Row between style={{ marginTop: 8 }}>
            <Txt variant="tiny">{feeLabel ?? 'Valor do JOGA'}</Txt>
            <Txt variant="num" style={{ fontSize: 17 }}>
              {cents(jogaCents)}
            </Txt>
          </Row>
          <View style={{ height: 1, backgroundColor: palette.line, marginVertical: 10 }} />
          <Row between>
            <Txt variant="h3">Total</Txt>
            <Txt variant="num" style={{ fontSize: 24 }}>
              {cents(totalCents)}
            </Txt>
          </Row>
        </>
      ) : null}
      {tickets != null ? (
        <Txt variant="tiny" style={{ marginTop: 6 }}>
          {tickets} ingressos consumidos nesta vaga
        </Txt>
      ) : null}
      {courtesy ? (
        <Notice tone="blue" icon="info">
          {fundingSource === 'pass'
            ? 'Cota do passe: a franquia mensal cobre a vaga. O JOGA não cobra a taxa do jogador.'
            : fundingSource === 'free_level'
              ? 'Ingresso grátis de nível: a temporada cobre a vaga. O JOGA não cobra a taxa do jogador.'
              : 'Cortesia: o JOGA não cobra a taxa do jogador.'}
        </Notice>
      ) : null}
    </Card>
  );
}

export function TicketConversionTable({ emphasis }: { emphasis?: FormatFamily }) {
  const { palette } = useTheme();
  return (
    <Card>
      <Txt variant="h3">Tabela de conversão</Txt>
      <Txt variant="tiny" style={{ marginTop: 4 }}>
        Ingressos por jogador. O servidor congela a quantidade e o preço na reserva.
      </Txt>
      <Row style={{ marginTop: 10 }}>
        <Txt variant="label" style={{ flex: 1.5 }}>
          Faixa
        </Txt>
        {([5, 6, 3] as FormatFamily[]).map((family) => (
          <Txt
            key={family}
            variant="label"
            style={{
              flex: 1,
              textAlign: 'center',
              color: emphasis && emphasis !== family ? palette.muted : undefined,
            }}
          >
            {family}x{family}
          </Txt>
        ))}
      </Row>
      {BAND_ORDER.map((code) => (
        <Row key={code} between style={{ paddingVertical: 8 }}>
          <View style={{ flex: 1.5 }}>
            <Txt variant="tiny">{BAND_LABELS[code]}</Txt>
            <Txt variant="tiny" color="soft">
              {BAND_RANGES[code]}
            </Txt>
          </View>
          {([5, 6, 3] as FormatFamily[]).map((family) => (
            <Txt
              key={family}
              variant="num"
              style={{
                flex: 1,
                textAlign: 'center',
                fontSize: 14,
                color: emphasis && emphasis !== family ? palette.muted : undefined,
              }}
            >
              {TICKETS_BY_BAND[family][code]}
            </Txt>
          ))}
        </Row>
      ))}
    </Card>
  );
}

export function participantPrice(
  participant: {
    contribution_cents: number;
    space_charge_cents: number;
    fee_charge_cents: number;
    funding_source: string | null;
  } | null,
) {
  if (!participant) {
    return null;
  }
  return {
    venueCents: participant.space_charge_cents,
    jogaCents: participant.fee_charge_cents,
    totalCents: participant.contribution_cents,
    fundingSource: participant.funding_source,
  };
}

export function bookingPrice(booking: {
  venue_price_cents: number;
  fee_cents: number;
  total_cents: number;
}) {
  return {
    venueCents: booking.venue_price_cents,
    jogaCents: booking.fee_cents,
    totalCents: booking.total_cents,
  };
}
