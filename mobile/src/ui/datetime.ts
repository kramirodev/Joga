const WEEKDAYS = ['dom', 'seg', 'ter', 'qua', 'qui', 'sex', 'sáb'];
export const WEEKDAY_NAMES = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];
const WEEKDAYS_FULL = [
  'domingo',
  'segunda-feira',
  'terça-feira',
  'quarta-feira',
  'quinta-feira',
  'sexta-feira',
  'sábado',
];
const MONTHS = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
const MONTHS_FULL = [
  'janeiro',
  'fevereiro',
  'março',
  'abril',
  'maio',
  'junho',
  'julho',
  'agosto',
  'setembro',
  'outubro',
  'novembro',
  'dezembro',
];

function parts(value: string | Date) {
  const date = typeof value === 'string' ? new Date(value) : value;
  return {
    date,
    day: date.getDate(),
    month: MONTHS[date.getMonth()],
    weekday: WEEKDAYS[date.getDay()],
    hours: String(date.getHours()).padStart(2, '0'),
    minutes: String(date.getMinutes()).padStart(2, '0'),
  };
}

export function shortDate(value: string | Date): string {
  const item = parts(value);
  return `${item.weekday}, ${item.day} ${item.month}`;
}

export function shortDateTime(value: string | Date): string {
  const item = parts(value);
  return `${item.weekday}, ${item.day} ${item.month} · ${item.hours}:${item.minutes}`;
}

function zonedParts(value: string | Date, timeZone: string) {
  const date = typeof value === 'string' ? new Date(value) : value;
  const formatter = new Intl.DateTimeFormat('pt-BR', {
    timeZone,
    weekday: 'short',
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
  const values = Object.fromEntries(
    formatter
      .formatToParts(date)
      .filter((part) => part.type !== 'literal')
      .map((part) => [part.type, part.value]),
  ) as Record<string, string>;
  return {
    weekday: (values.weekday ?? '').replace('.', '').toLowerCase(),
    day: values.day ?? '--',
    month: MONTHS[Math.max(0, Number(values.month) - 1)] ?? '',
    hours: (values.hour ?? '00').replace('24', '00'),
    minutes: values.minute ?? '00',
  };
}

/** Formata no fuso IANA do estabelecimento, nunca no fuso do aparelho. */
export function zonedShortDateTime(value: string | Date, timeZone: string | null): string {
  if (!timeZone) {
    return shortDateTime(value);
  }
  try {
    const item = zonedParts(value, timeZone);
    return `${item.weekday}, ${item.day} ${item.month} · ${item.hours}:${item.minutes}`;
  } catch {
    return shortDateTime(value);
  }
}

export function zonedTimeOnly(value: string | Date, timeZone: string | null): string {
  if (!timeZone) {
    return timeOnly(value);
  }
  try {
    const item = zonedParts(value, timeZone);
    return `${item.hours}:${item.minutes}`;
  } catch {
    return timeOnly(value);
  }
}

export function zonedDateOnly(value: string | Date, timeZone: string | null): string {
  if (!timeZone) {
    return dateOnly(value);
  }
  try {
    const item = zonedParts(value, timeZone);
    return `${item.day} ${item.month}`;
  } catch {
    return dateOnly(value);
  }
}

export function timeOnly(value: string | Date): string {
  const item = parts(value);
  return `${item.hours}:${item.minutes}`;
}

export function dateOnly(value: string | Date): string {
  const item = parts(value);
  return `${item.day} ${item.month}`;
}

export function fullWeekday(value: string | Date): string {
  const item = parts(value);
  return item.weekday.charAt(0).toUpperCase() + item.weekday.slice(1);
}

export function longDate(value: string | Date = new Date()): string {
  const date = typeof value === 'string' ? new Date(value) : value;
  const weekday = WEEKDAYS_FULL[date.getDay()];
  return `${weekday.charAt(0).toUpperCase()}${weekday.slice(1)}, ${date.getDate()} de ${MONTHS_FULL[date.getMonth()]}`;
}

export function countdown(target: string | Date, now = new Date()): string {
  const end = typeof target === 'string' ? new Date(target) : target;
  const diff = Math.max(0, end.getTime() - now.getTime());
  const hours = Math.floor(diff / 3_600_000);
  const minutes = Math.ceil((diff % 3_600_000) / 60_000);
  if (hours >= 24) {
    const days = Math.floor(hours / 24);
    return `${days}d ${hours % 24}h`;
  }
  return `${hours}h ${minutes}min`;
}

function plural(value: number, singular: string, pluralForm: string): string {
  return `${value} ${value === 1 ? singular : pluralForm}`;
}

/**
 * Contagem regressiva da temporada para o perfil.
 *
 * `ends_at` é UTC e só o relativo é exibido. Data ausente/inválida devolve
 * `null` para a tela manter o texto fixo de fallback. O texto curto nunca
 * mostra número negativo.
 */
export function formatSeasonCountdown(
  endsAt: string | null | undefined,
  now: Date = new Date(),
): { short: string; long: string } | null {
  if (!endsAt) {
    return null;
  }
  const end = new Date(endsAt).getTime();
  if (!Number.isFinite(end)) {
    return null;
  }
  const diff = end - now.getTime();
  if (diff <= 0) {
    return { short: 'Temporada encerrada', long: 'A temporada terminou' };
  }
  const days = Math.floor(diff / 86_400_000);
  const hours = Math.floor((diff % 86_400_000) / 3_600_000);
  const minutes = Math.floor((diff % 3_600_000) / 60_000);
  if (days >= 1) {
    const short = hours >= 1 ? `${days}d ${hours}h` : `${days}d`;
    const long =
      hours >= 1
        ? `${plural(days, 'dia', 'dias')} e ${plural(hours, 'hora', 'horas')}`
        : plural(days, 'dia', 'dias');
    return { short: `Termina em ${short}`, long: `A temporada termina em ${long}` };
  }
  if (hours >= 1) {
    const short = minutes >= 1 ? `${hours}h ${minutes}min` : `${hours}h`;
    const long =
      minutes >= 1
        ? `${plural(hours, 'hora', 'horas')} e ${plural(minutes, 'minuto', 'minutos')}`
        : plural(hours, 'hora', 'horas');
    return { short: `Termina em ${short}`, long: `A temporada termina em ${long}` };
  }
  if (minutes >= 1) {
    return {
      short: `Termina em ${minutes}min`,
      long: `A temporada termina em ${plural(minutes, 'minuto', 'minutos')}`,
    };
  }
  return { short: 'Encerrando…', long: 'A temporada está encerrando' };
}

export function elapsed(since: string | Date, now = new Date()): string {
  const start = typeof since === 'string' ? new Date(since) : since;
  const diff = Math.max(0, now.getTime() - start.getTime());
  const minutes = Math.floor(diff / 60_000);
  const seconds = Math.floor((diff % 60_000) / 1000);
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

export function clock(target: string | Date, now = new Date()): string {
  const end = typeof target === 'string' ? new Date(target) : target;
  const diff = Math.max(0, end.getTime() - now.getTime());
  const minutes = Math.floor(diff / 60_000);
  const seconds = Math.floor((diff % 60_000) / 1000);
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

export function cents(value: number): string {
  return (value / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

export function number(value: number): string {
  return value.toLocaleString('pt-BR');
}

export function levelLabel(level: string): string {
  if (level === 'beginner') {
    return 'Iniciante';
  }
  if (level === 'advanced') {
    return 'Avançado';
  }
  if (level === 'intermediate') {
    return 'Intermediário';
  }
  return level;
}

export function divisionLabel(division: string): string {
  const map: Record<string, string> = {
    BRONZE: 'Bronze',
    SILVER: 'Prata',
    GOLD: 'Ouro',
    PLATINUM: 'Platina',
    DIAMOND: 'Diamante',
    PROVISIONAL: 'Provisório',
  };
  return map[division] ?? division;
}

export function courtLabel(value: string): string {
  if (value === 'PUBLIC_ONLY') {
    return 'Públicas';
  }
  if (value === 'PRIVATE_ONLY') {
    return 'Particulares';
  }
  return 'Tanto faz';
}

export function levelFromLabel(value: string): 'beginner' | 'intermediate' | 'advanced' {
  if (value === 'Iniciante') {
    return 'beginner';
  }
  if (value === 'Avançado') {
    return 'advanced';
  }
  return 'intermediate';
}

export function courtFromLabel(value: string): 'PUBLIC_ONLY' | 'PRIVATE_ONLY' | 'ANY' {
  if (value === 'Públicas') {
    return 'PUBLIC_ONLY';
  }
  if (value === 'Particulares') {
    return 'PRIVATE_ONLY';
  }
  return 'ANY';
}
