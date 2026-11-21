import type { BookableVenue, Sport } from '../api/types';

/**
 * Estado puro dos filtros de quadras. Cobertura, distância e formato são
 * aplicados **no servidor** (`GET /discovery/bookable-venues`); a busca textual
 * não tem parâmetro no contrato e roda sobre o conjunto baixado.
 */

export type VenueCoverage = 'any' | 'covered' | 'open';

export type VenueFilters = {
  coverage: VenueCoverage;
  maxKm: number | null;
  formatId: string | null;
};

export const DEFAULT_VENUE_FILTERS: VenueFilters = {
  coverage: 'any',
  maxKm: null,
  formatId: null,
};

export const VENUE_DISTANCE_OPTIONS = [5, 10, 25] as const;

export function isDefaultFilters(filters: VenueFilters): boolean {
  return (
    filters.coverage === DEFAULT_VENUE_FILTERS.coverage &&
    filters.maxKm === DEFAULT_VENUE_FILTERS.maxKm &&
    filters.formatId === DEFAULT_VENUE_FILTERS.formatId
  );
}

/** Igualdade por valor: aplicar o mesmo rascunho não dispara nova consulta. */
export function filtersEqual(left: VenueFilters, right: VenueFilters): boolean {
  return (
    left.coverage === right.coverage &&
    left.maxKm === right.maxKm &&
    left.formatId === right.formatId
  );
}

export type VenueFilterChip = {
  key: 'format' | 'coverage' | 'distance';
  label: string;
};

/** Chips do resumo derivados do estado; "Tanto faz" nunca aparece. */
export function filterChips(
  filters: VenueFilters,
  formatLabel: (formatId: string) => string,
): VenueFilterChip[] {
  const chips: VenueFilterChip[] = [];
  if (filters.formatId) {
    chips.push({ key: 'format', label: formatLabel(filters.formatId) });
  }
  if (filters.coverage !== 'any') {
    chips.push({
      key: 'coverage',
      label: filters.coverage === 'covered' ? 'Coberta' : 'Aberta',
    });
  }
  if (filters.maxKm != null) {
    chips.push({ key: 'distance', label: `Até ${filters.maxKm} km` });
  }
  return chips;
}

/** Parâmetros reais aceitos pelo discovery; nunca inventa chave desconhecida. */
export function venueFilterParams(filters: VenueFilters): {
  format_id?: string;
  covered?: boolean;
  max_distance_km?: number;
} {
  return {
    ...(filters.formatId ? { format_id: filters.formatId } : {}),
    ...(filters.coverage === 'covered'
      ? { covered: true }
      : filters.coverage === 'open'
        ? { covered: false }
        : {}),
    ...(filters.maxKm != null ? { max_distance_km: filters.maxKm } : {}),
  };
}

/** Opções de esporte/formato vêm do catálogo, nunca de nome adivinhado. */
export function formatOptions(catalog: Sport[]): {
  id: string;
  label: string;
  sportName: string;
}[] {
  return catalog.flatMap((sport) =>
    sport.formats.map((format) => ({
      id: format.id,
      label: format.name,
      sportName: sport.name,
    })),
  );
}

export function formatOptionLabel(catalog: Sport[], formatId: string | null): string {
  if (!formatId) {
    return 'Esporte';
  }
  return formatOptions(catalog).find((format) => format.id === formatId)?.label ?? 'Esporte';
}

/** Normaliza acento, caixa e espaços para comparar busca sem exigir grafia exata. */
export function normalizeSearch(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * Busca textual no conjunto já baixado. Quando a busca está ativa a tela baixa
 * o conjunto completo (até o limite declarado), nunca só a página atual.
 */
export function searchVenues(venues: BookableVenue[], query: string): BookableVenue[] {
  const term = normalizeSearch(query);
  if (!term) {
    return venues;
  }
  return venues.filter((venue) => {
    const fields = [
      venue.name,
      venue.city,
      venue.state,
      venue.address_line ?? '',
      ...(venue.sports ?? []).flatMap((sport) => [sport.name, sport.sport_name]),
    ];
    return fields.some((value) => normalizeSearch(value).includes(term));
  });
}
