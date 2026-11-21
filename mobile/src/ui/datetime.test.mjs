import assert from 'node:assert/strict';
import test from 'node:test';

import { formatSeasonCountdown } from './datetime.ts';

const NOW = new Date('2026-11-21T00:00:00Z');
const DAY = 86_400_000;
const HOUR = 3_600_000;
const MINUTE = 60_000;

function endsAt(offsetMs) {
  return new Date(NOW.getTime() + offsetMs).toISOString();
}

test('>= 1 dia mostra dias e horas', () => {
  assert.deepEqual(formatSeasonCountdown(endsAt(12 * DAY + 4 * HOUR + 5 * MINUTE), NOW), {
    short: 'Termina em 12d 4h',
    long: 'A temporada termina em 12 dias e 4 horas',
  });
  assert.equal(formatSeasonCountdown(endsAt(24 * HOUR), NOW).short, 'Termina em 1d');
});

test('>= 1 hora mostra horas e minutos', () => {
  assert.deepEqual(formatSeasonCountdown(endsAt(3 * HOUR + 20 * MINUTE), NOW), {
    short: 'Termina em 3h 20min',
    long: 'A temporada termina em 3 horas e 20 minutos',
  });
  assert.equal(formatSeasonCountdown(endsAt(60 * MINUTE), NOW).short, 'Termina em 1h');
});

test('>= 1 minuto mostra minutos', () => {
  assert.deepEqual(formatSeasonCountdown(endsAt(8 * MINUTE + 30_000), NOW), {
    short: 'Termina em 8min',
    long: 'A temporada termina em 8 minutos',
  });
  assert.equal(formatSeasonCountdown(endsAt(60_000), NOW).short, 'Termina em 1min');
});

test('< 1 minuto encerra e data no passado não mostra número negativo', () => {
  assert.equal(formatSeasonCountdown(endsAt(30_000), NOW).short, 'Encerrando…');
  assert.equal(formatSeasonCountdown(endsAt(-1), NOW).short, 'Temporada encerrada');
  assert.equal(formatSeasonCountdown(endsAt(-1), NOW).long, 'A temporada terminou');
});

test('data ausente ou inválida devolve null para manter o fallback', () => {
  assert.equal(formatSeasonCountdown(null, NOW), null);
  assert.equal(formatSeasonCountdown(undefined, NOW), null);
  assert.equal(formatSeasonCountdown('', NOW), null);
  assert.equal(formatSeasonCountdown('não é data', NOW), null);
});

test('ends_at é lido como UTC e exibido só em relativo', () => {
  assert.deepEqual(formatSeasonCountdown('2026-11-22T04:00:00Z', NOW), {
    short: 'Termina em 1d 4h',
    long: 'A temporada termina em 1 dia e 4 horas',
  });
});
