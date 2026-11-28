import type { PassSubscription, TicketLot } from '../api/types';

/** Rótulos da assinatura (ADR 0070) usados na carteira, catálogo e recibo. */

export function planDurationLabel(months: number): string {
  if (!Number.isFinite(months) || months <= 0) {
    return 'duração não informada';
  }
  return months === 1 ? '1 mês' : `${months} meses`;
}

export function planCycleName(months: number): string {
  if (months === 1) return 'Mensal';
  if (months === 3) return 'Trimestral';
  if (months === 6) return 'Semestral';
  return planDurationLabel(months);
}

export function planInstallmentsLabel(installments: number): string {
  if (!Number.isFinite(installments) || installments <= 1) {
    return 'à vista no Pix';
  }
  return `${installments} parcelas`;
}

export function passStatusLabel(status: string | null | undefined): string {
  const value = (status ?? '').toUpperCase();
  if (value === 'ACTIVE') return 'ATIVA';
  if (value === 'PENDING') return 'AGUARDANDO PAGAMENTO';
  if (value === 'EXPIRED') return 'EXPIRADA';
  if (value === 'CANCELLED' || value === 'CANCELED') return 'CANCELADA';
  if (value === 'REFUNDED') return 'ESTORNADA';
  return value || 'SEM ASSINATURA';
}

export function cycleStatusLabel(status: string | null | undefined): string {
  const value = (status ?? '').toUpperCase();
  if (value === 'DELIVERED') return 'Entregue';
  if (value === 'SCHEDULED') return 'Agendado';
  if (value === 'CLOSED') return 'Encerrado';
  if (value === 'CANCELLED' || value === 'CANCELED') return 'Cancelado';
  return value ? value.toLowerCase() : '—';
}

/**
 * Crédito comprado antes da assinatura. Nunca expira e não é convertido nem
 * somado à franquia do ciclo.
 */
export function legacyTickets(lots: TicketLot[]): number {
  return lots.reduce(
    (total, lot) =>
      lot.source === 'purchase' || lot.source === 'refund' ? total + lot.remaining : total,
    0,
  );
}

/** Ingressos promocionais de temporada/nível; expiram com a temporada. */
export function freeTickets(lots: TicketLot[]): number {
  return lots.reduce(
    (total, lot) =>
      lot.source === 'free' || lot.source === 'free_level' ? total + lot.remaining : total,
    0,
  );
}

/** O recibo interno só existe depois do pagamento confirmado. */
export function receiptAvailable(subscription: PassSubscription | null | undefined): boolean {
  if (!subscription) {
    return false;
  }
  return Boolean(subscription.paid_at || subscription.payment?.paid);
}
