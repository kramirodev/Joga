import assert from 'node:assert/strict';
import test from 'node:test';

import {
  formatDateShort,
  formatDateTimeShort,
  formatSeasonCountdown,
  formatTime,
  greetingForHour,
} from './datetime.ts';

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

test('ISO UTC vira hora local do aparelho: 04:54Z é 01:54 em São Paulo', () => {
  assert.equal(formatTime('2026-11-21T04:54:00Z', 'America/Sao_Paulo'), '01:54');
  assert.equal(formatDateShort('2026-11-21T04:54:00Z', 'America/Sao_Paulo'), '21 nov');
  assert.equal(
    formatDateTimeShort('2026-11-21T04:54:00Z', 'America/Sao_Paulo'),
    'sáb, 21 nov · 01:54',
  );
});

test('virada de dia usa o dia local, não o dia UTC', () => {
  assert.equal(formatTime('2026-11-21T02:00:00Z', 'America/Sao_Paulo'), '23:00');
  assert.equal(formatDateShort('2026-11-21T02:00:00Z', 'America/Sao_Paulo'), '20 nov');
  assert.equal(
    formatDateTimeShort('2026-11-21T02:00:00Z', 'America/Sao_Paulo'),
    'sex, 20 nov · 23:00',
  );
});

test('sem timeZone explícito usa o fuso do aparelho', () => {
  const iso = '2026-11-21T04:54:00Z';
  const local = new Date(iso);
  const expected = `${String(local.getHours()).padStart(2, '0')}:${String(local.getMinutes()).padStart(2, '0')}`;
  assert.equal(formatTime(iso), expected);
});

test('valor ausente ou inválido devolve string vazia, sem Invalid Date', () => {
  for (const value of ['', null, undefined, 'não é data']) {
    assert.equal(formatTime(value), '');
    assert.equal(formatDateShort(value), '');
    assert.equal(formatDateTimeShort(value), '');
  }
  assert.equal(
    formatTime('2026-11-21T04:54:00Z', 'Fuso/Inexistente'),
    formatTime('2026-11-21T04:54:00Z'),
  );
});

test('saudação segue a hora local por faixa', () => {
  const expected = {
    0: 'Boa noite',
    4: 'Boa noite',
    5: 'Bom dia',
    11: 'Bom dia',
    12: 'Boa tarde',
    17: 'Boa tarde',
    18: 'Boa noite',
    23: 'Boa noite',
  };
  for (const [hour, greeting] of Object.entries(expected)) {
    assert.equal(greetingForHour(Number(hour)), greeting, `hora ${hour}`);
  }
  assert.equal(greetingForHour(24), 'Boa noite');
  assert.equal(greetingForHour(5.9), 'Bom dia');
});
