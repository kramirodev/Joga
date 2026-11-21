import assert from 'node:assert/strict';
import test from 'node:test';

import {
  DEFAULT_VENUE_FILTERS,
  filterChips,
  filtersEqual,
  formatOptionLabel,
  formatOptions,
  isDefaultFilters,
  normalizeSearch,
  searchVenues,
  venueFilterParams,
} from './venueFilters.ts';

const catalog = [
  {
    id: 'sport-1',
    slug: 'futebol',
    name: 'Futebol',
    formats: [
      {
        id: 'format-futebol-5x5',
        slug: 'futebol-5x5',
        name: 'Futebol 5x5',
        team_size: 5,
        total_participants: 10,
        play_minutes: 50,
        break_minutes: 10,
        duration_minutes: 60,
        version: 1,
      },
    ],
  },
  {
    id: 'sport-2',
    slug: 'volei',
    name: 'Vôlei',
    formats: [
      {
        id: 'format-volei-6x6',
        slug: 'volei-6x6',
        name: 'Vôlei 6x6',
        team_size: 6,
        total_participants: 12,
        play_minutes: 50,
        break_minutes: 10,
        duration_minutes: 60,
        version: 1,
      },
    ],
  },
];

const venue = (patch) => ({
  id: 'venue-1',
  organization_id: 'org-1',
  name: 'Arena Central',
  city: 'São Paulo',
  state: 'SP',
  address_line: 'Rua do Centro, 10',
  latitude: null,
  longitude: null,
  timezone: 'America/Sao_Paulo',
  covered: true,
  spaces_count: 2,
  min_price_cents: 0,
  min_tickets: 0,
  distance_km: 3.2,
  photo_url: null,
  sports: [
    {
      sport_id: 'sport-1',
      sport_name: 'Futebol',
      format_id: 'format-futebol-5x5',
      name: 'Futebol 5x5',
    },
  ],
  ...patch,
});

test('estado inicial não tem recorte', () => {
  assert.equal(isDefaultFilters(DEFAULT_VENUE_FILTERS), true);
  assert.deepEqual(venueFilterParams(DEFAULT_VENUE_FILTERS), {});
  assert.deepEqual(
    filterChips(DEFAULT_VENUE_FILTERS, () => 'x'),
    [],
  );
});

test('aplicar o mesmo rascunho não muda o estado', () => {
  assert.equal(filtersEqual(DEFAULT_VENUE_FILTERS, { ...DEFAULT_VENUE_FILTERS }), true);
  assert.equal(
    filtersEqual(DEFAULT_VENUE_FILTERS, { ...DEFAULT_VENUE_FILTERS, coverage: 'covered' }),
    false,
  );
  assert.equal(
    filtersEqual({ ...DEFAULT_VENUE_FILTERS, maxKm: 10 }, { ...DEFAULT_VENUE_FILTERS, maxKm: 5 }),
    false,
  );
});

test('cobertura vira covered booleano e nunca filtro local', () => {
  assert.deepEqual(venueFilterParams({ ...DEFAULT_VENUE_FILTERS, coverage: 'covered' }), {
    covered: true,
  });
  assert.deepEqual(venueFilterParams({ ...DEFAULT_VENUE_FILTERS, coverage: 'open' }), {
    covered: false,
  });
  assert.deepEqual(venueFilterParams({ ...DEFAULT_VENUE_FILTERS, coverage: 'any' }), {});
});

test('distância e formato usam as chaves reais do discovery', () => {
  assert.deepEqual(
    venueFilterParams({
      coverage: 'any',
      maxKm: 10,
      formatId: 'format-futebol-5x5',
    }),
    { format_id: 'format-futebol-5x5', max_distance_km: 10 },
  );
  assert.equal(isDefaultFilters({ ...DEFAULT_VENUE_FILTERS, maxKm: 5 }), false);
});

test('chips refletem só o que está comprometido', () => {
  assert.deepEqual(
    filterChips(
      { coverage: 'covered', maxKm: 5, formatId: 'format-futebol-5x5' },
      () => 'Futebol 5x5',
    ),
    [
      { key: 'format', label: 'Futebol 5x5' },
      { key: 'coverage', label: 'Coberta' },
      { key: 'distance', label: 'Até 5 km' },
    ],
  );
  assert.deepEqual(
    filterChips({ coverage: 'open', maxKm: null, formatId: null }, () => 'x'),
    [{ key: 'coverage', label: 'Aberta' }],
  );
});

test('busca ignora acento, caixa e espaços repetidos', () => {
  assert.equal(normalizeSearch('  São   PAULO '), 'sao paulo');
  const venues = [venue({})];
  assert.deepEqual(
    searchVenues(venues, 'sao paulo').map((item) => item.id),
    ['venue-1'],
  );
  assert.deepEqual(
    searchVenues(venues, 'CENTRO').map((item) => item.id),
    ['venue-1'],
  );
  assert.deepEqual(
    searchVenues(venues, 'futebol').map((item) => item.id),
    ['venue-1'],
  );
  assert.deepEqual(searchVenues(venues, 'rio de janeiro'), []);
});

test('busca vazia devolve o conjunto inteiro', () => {
  const venues = [venue({ id: 'a' }), venue({ id: 'b' })];
  assert.equal(searchVenues(venues, '   ').length, 2);
});

test('opções e rótulo de formato vêm do catálogo', () => {
  assert.deepEqual(
    formatOptions(catalog).map((item) => item.id),
    ['format-futebol-5x5', 'format-volei-6x6'],
  );
  assert.equal(formatOptionLabel(catalog, 'format-volei-6x6'), 'Vôlei 6x6');
  assert.equal(formatOptionLabel(catalog, null), 'Esporte');
  assert.equal(formatOptionLabel(catalog, 'desconhecido'), 'Esporte');
});
