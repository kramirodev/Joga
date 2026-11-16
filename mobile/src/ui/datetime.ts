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
