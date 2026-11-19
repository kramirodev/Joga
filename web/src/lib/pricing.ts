/**
 * Cálculos de exibição da tabela 2D (ADR 0049 §13).
 *
 * A API é a autoridade: estes helpers só antecipam a prévia do painel e
 * bloqueiam uma edição que violaria o invariante antes de chegar ao servidor.
 * O modo é sempre explícito: `standard` aplica 20%; `contingency` não aplica.
 */

export const TICKET_CALIBRATION_CENTS = 310;

export type PricingMode = "standard" | "contingency";

export function seatsForTeamSize(teamSize: number): number {
  return Math.max(0, teamSize) * 2;
}

export function requiredTotalCents(venuePriceCents: number, mode: PricingMode): number {
  if (venuePriceCents <= 0) return 0;
  return mode === "standard" ? Math.ceil((venuePriceCents * 6) / 5) : venuePriceCents;
}

/** Menor k que cobre o total exigido por jogador no modo informado. */
export function minimumTickets(
  venuePriceCents: number,
  teamSize: number,
  mode: PricingMode,
): number {
  const seats = seatsForTeamSize(teamSize);
  const total = requiredTotalCents(venuePriceCents, mode);
  if (total <= 0 || seats <= 0) return 0;
  return Math.ceil(total / (seats * TICKET_CALIBRATION_CENTS));
}

export function pricePerPlayerCents(tickets: number): number {
  return Math.max(0, tickets) * TICKET_CALIBRATION_CENTS;
}

/** `k × 3,10 × jogadores ≥ total exigido pelo modo`. */
export function ticketsCoverInvariant(
  venuePriceCents: number,
  teamSize: number,
  tickets: number,
  mode: PricingMode,
): boolean {
  const seats = seatsForTeamSize(teamSize);
  const total = requiredTotalCents(venuePriceCents, mode);
  if (total <= 0 || seats <= 0) return false;
  return tickets * TICKET_CALIBRATION_CENTS * seats >= total;
}

export function ticketsInvariantError(
  venuePriceCents: number,
  teamSize: number,
  tickets: number,
  mode: PricingMode,
): string | null {
  if (!Number.isInteger(tickets) || tickets < 1 || tickets > 1_000) {
    return "Informe um número inteiro de tickets entre 1 e 1.000.";
  }
  if (!ticketsCoverInvariant(venuePriceCents, teamSize, tickets, mode)) {
    const minimum = minimumTickets(venuePriceCents, teamSize, mode);
    return `Essa quantidade não cobre o preço no modo ${
      mode === "standard" ? "padrão" : "contingência"
    }. O mínimo para ${teamSize}x${teamSize} é ${minimum}.`;
  }
  return null;
}
