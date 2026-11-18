/**
 * Tabela 2D da ADR 0049 §13 e rótulos de ticket.
 *
 * A tabela é unidade de consumo e exibição; o preço jurídico é sempre o valor
 * do espaço + taxa congelados pelo servidor. O app nunca calcula a taxa de
 * intermediação: aqui só existem os valores públicos da tabela e o valor de
 * referência do ticket (R$ 3,10) usado para exibir a estimativa antes de o
 * servidor congelar `venue_price_cents`, `fee_charge_cents` e `total_cents`.
 */

export const TICKET_REFERENCE_CENTS = 310;

export type FormatFamily = 3 | 5 | 6;

export const BAND_ORDER = [
  'economica_dia',
  'economica_noite',
  'padrao_dia',
  'padrao_noite',
  'coberta',
  'premium',
] as const;

export type BandCode = (typeof BAND_ORDER)[number];

export const BAND_LABELS: Record<BandCode, string> = {
  economica_dia: 'Econômica dia',
  economica_noite: 'Econômica noite',
  padrao_dia: 'Padrão dia',
  padrao_noite: 'Padrão noite',
  coberta: 'Coberta',
  premium: 'Premium',
};

export const BAND_RANGES: Record<BandCode, string> = {
  economica_dia: 'até R$ 120',
  economica_noite: 'R$ 121–150',
  padrao_dia: 'R$ 151–180',
  padrao_noite: 'R$ 181–220',
  coberta: 'R$ 221–260',
  premium: 'R$ 261–300',
};

export const TICKETS_BY_BAND: Record<FormatFamily, Record<BandCode, number>> = {
  5: {
    economica_dia: 5,
    economica_noite: 6,
    padrao_dia: 7,
    padrao_noite: 9,
    coberta: 11,
    premium: 12,
  },
  6: {
    economica_dia: 4,
    economica_noite: 5,
    padrao_dia: 6,
    padrao_noite: 8,
    coberta: 9,
    premium: 10,
  },
  3: {
    economica_dia: 8,
    economica_noite: 10,
    padrao_dia: 12,
    padrao_noite: 15,
    coberta: 17,
    premium: 20,
  },
};

export const FORMAT_LABELS: Record<FormatFamily, string> = {
  5: '5x5 · futebol · 10 jogadores',
  6: '6x6 · vôlei · 12 jogadores',
  3: '3x3 · futevôlei · 6 jogadores',
};

export function bandLabel(code: string | null | undefined): string {
  if (!code) {
    return 'Faixa a definir';
  }
  return BAND_LABELS[code as BandCode] ?? code.replaceAll('_', ' ');
}

export function formatFamily(formatName: string | null | undefined): FormatFamily | null {
  if (!formatName) {
    return null;
  }
  const match = formatName.match(/(\d+)\s*x\s*(\d+)/i);
  if (!match) {
    return null;
  }
  const teamSize = Number(match[1]);
  if (teamSize === 3 || teamSize === 5 || teamSize === 6) {
    return teamSize;
  }
  return null;
}

export function ticketsForBand(
  family: FormatFamily,
  code: string | null | undefined,
): number | null {
  if (!code) {
    return null;
  }
  return TICKETS_BY_BAND[family][code as BandCode] ?? null;
}

/**
 * Estimativa exibida antes da criação da reserva. O servidor congela os valores
 * reais; esta função não aplica percentual de taxa.
 */
export function referenceBreakdown(tickets: number, venuePriceCents: number) {
  const totalCents = tickets * TICKET_REFERENCE_CENTS;
  return {
    totalCents,
    jogaCents: Math.max(0, totalCents - venuePriceCents),
  };
}

export function fundingSourceLabel(source: string | null | undefined): string | null {
  if (source === 'credit') return 'Crédito';
  if (source === 'pass') return 'Cota do passe';
  if (source === 'free_level') return 'Ingresso de nível';
  if (source === 'admin') return 'Cortesia';
  if (source === 'pix') return 'Pix';
  return null;
}
