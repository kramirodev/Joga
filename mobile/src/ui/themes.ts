import { dark, light, type Palette } from './theme.ts';

export type ThemeArtKey =
  'noite-quadra' | 'golden-hour' | 'dia-de-jogo' | 'ceu-vermelho' | 'ceu-claro';

export type ThemeId =
  | 'claro'
  | 'escuro'
  | 'noite-quadra'
  | 'golden-hour'
  | 'dia-de-jogo'
  | 'ceu-vermelho'
  | 'ceu-claro';

export type Theme = {
  id: ThemeId;
  /** Nome curto em pt-BR mostrado no seletor. */
  name: string;
  dark: boolean;
  palette: Palette;
  art: ThemeArtKey;
};

const noiteQuadra: Palette = {
  bg: '#070B16',
  surface: '#0D1524',
  surface2: '#121D31',
  surface3: '#182640',
  ink: '#EAF2FF',
  inkSoft: '#9CB3CE',
  muted: '#A9BED8',
  subtle: '#7E94B2',
  line: '#1D2B42',
  lineSubtle: '#2A3C58',
  lineStrong: '#7A93B4',
  lime: '#38F2C8',
  limeDeep: '#7AFFDF',
  limeSoft: '#102C2C',
  brand: '#38F2C8',
  brandStrong: '#8CFFE6',
  brandInk: '#03130F',
  focus: '#8CFFE6',
  blue: '#7AA7FF',
  blueSoft: '#12213F',
  green: '#5BE3B8',
  greenSoft: '#0F2A26',
  orange: '#FFC46B',
  orangeSoft: '#2C2213',
  red: '#FF8C8C',
  redSoft: '#2E161B',
  success: '#5BE3B8',
  warning: '#FFC46B',
  danger: '#FF8C8C',
  info: '#7AA7FF',
  onInk: '#EAF2FF',
  softOnInk: '#A9BED8',
  lineOnInk: '#2A3C58',
  heat1: '#0D1524',
  heat2: '#121D31',
  heat3: '#7E94B2',
  heat4: '#38F2C8',
  progressTrack: '#1D2B42',
};

const goldenHour: Palette = {
  bg: '#160B26',
  surface: '#211231',
  surface2: '#2B183F',
  surface3: '#3A2153',
  ink: '#FFF3DC',
  inkSoft: '#D3B7DA',
  muted: '#D8C0DE',
  subtle: '#B298BE',
  line: '#3B2452',
  lineSubtle: '#4A2F63',
  lineStrong: '#B08FC2',
  lime: '#FFC94A',
  limeDeep: '#FFE08A',
  limeSoft: '#3A2917',
  brand: '#FFC94A',
  brandStrong: '#FFE08A',
  brandInk: '#221403',
  focus: '#FFE08A',
  blue: '#9DB8FF',
  blueSoft: '#241F44',
  green: '#8FE0B0',
  greenSoft: '#1B3225',
  orange: '#FF9F35',
  orangeSoft: '#3A2410',
  red: '#FF8A8A',
  redSoft: '#3A1620',
  success: '#8FE0B0',
  warning: '#FFC94A',
  danger: '#FF8A8A',
  info: '#9DB8FF',
  onInk: '#FFF3DC',
  softOnInk: '#D8C0DE',
  lineOnInk: '#4A2F63',
  heat1: '#211231',
  heat2: '#2B183F',
  heat3: '#B298BE',
  heat4: '#FFC94A',
  progressTrack: '#3B2452',
};

const diaDeJogo: Palette = {
  bg: '#F6EDDC',
  surface: '#FFFBF2',
  surface2: '#EFE2C9',
  surface3: '#E7D6B8',
  ink: '#1C241C',
  inkSoft: '#58614F',
  muted: '#555F4C',
  subtle: '#5F6A53',
  line: '#DCCDAF',
  lineSubtle: '#E5D9C0',
  lineStrong: '#8C8168',
  lime: '#2F5540',
  limeDeep: '#3C6B50',
  limeSoft: '#DDE9DB',
  brand: '#2F5540',
  brandStrong: '#8FBE9C',
  brandInk: '#FFFBF2',
  focus: '#2F5540',
  blue: '#2B5B75',
  blueSoft: '#DAE8EF',
  green: '#2F6B4B',
  greenSoft: '#DDE9DB',
  orange: '#7A4A12',
  orangeSoft: '#F5E2C4',
  red: '#A33127',
  redSoft: '#F5DCD3',
  success: '#2F6B4B',
  warning: '#7A4A12',
  danger: '#A33127',
  info: '#2B5B75',
  onInk: '#FFFBF2',
  softOnInk: '#D6CBB3',
  lineOnInk: '#4A4534',
  heat1: '#EFE2C9',
  heat2: '#E5D9C0',
  heat3: '#8A8B77',
  heat4: '#2F5540',
  progressTrack: '#DCCDAF',
};

const ceuVermelho: Palette = {
  bg: '#080104',
  surface: '#150409',
  surface2: '#1F060C',
  surface3: '#2C0911',
  ink: '#FFEDEB',
  inkSoft: '#CFA4A4',
  muted: '#D9B2B1',
  subtle: '#B38282',
  line: '#3A0D14',
  lineSubtle: '#4E121B',
  lineStrong: '#B65A62',
  lime: '#FF5C63',
  limeDeep: '#FF9AA0',
  limeSoft: '#2C0911',
  brand: '#FF5C63',
  brandStrong: '#FF9AA0',
  brandInk: '#1A0204',
  focus: '#FF9AA0',
  blue: '#9DB8FF',
  blueSoft: '#1A1630',
  green: '#8FD9B8',
  greenSoft: '#10281F',
  orange: '#FFC46B',
  orangeSoft: '#2E2110',
  red: '#FF8A80',
  redSoft: '#2C0911',
  success: '#8FD9B8',
  warning: '#FFC46B',
  danger: '#FF8A80',
  info: '#9DB8FF',
  onInk: '#FFEDEB',
  softOnInk: '#D9B2B1',
  lineOnInk: '#4E121B',
  heat1: '#150409',
  heat2: '#1F060C',
  heat3: '#B38282',
  heat4: '#FF5C63',
  progressTrack: '#3A0D14',
};

const ceuClaro: Palette = {
  bg: '#F4F0E8',
  surface: '#FDFBF7',
  surface2: '#ECE6DC',
  surface3: '#E4DDD1',
  ink: '#241B17',
  inkSoft: '#625A53',
  muted: '#5F574F',
  subtle: '#6F675E',
  line: '#DCD3C6',
  lineSubtle: '#E5DED2',
  lineStrong: '#968A7B',
  lime: '#B3261E',
  limeDeep: '#8F1D17',
  limeSoft: '#F2DCD7',
  brand: '#B3261E',
  brandStrong: '#FF9C90',
  brandInk: '#FFF9F5',
  focus: '#B3261E',
  blue: '#2C5D7A',
  blueSoft: '#DDE8EE',
  green: '#2F6A4C',
  greenSoft: '#DCE8DE',
  orange: '#7C4A12',
  orangeSoft: '#F3E1C4',
  red: '#A32820',
  redSoft: '#F2DBD6',
  success: '#2F6A4C',
  warning: '#7C4A12',
  danger: '#A32820',
  info: '#2C5D7A',
  onInk: '#FFF9F5',
  softOnInk: '#D9CFC6',
  lineOnInk: '#4A413A',
  heat1: '#ECE6DC',
  heat2: '#E5DED2',
  heat3: '#948B81',
  heat4: '#B3261E',
  progressTrack: '#DCD3C6',
};

/**
 * Catálogo único de temas. A ordem é a do seletor: as duas bases primeiro e
 * depois as artes. `claro` fica em primeiro para ser o fallback de id inválido.
 */
export const themes: Theme[] = [
  { id: 'claro', name: 'Claro', dark: false, palette: light, art: 'ceu-claro' },
  { id: 'escuro', name: 'Escuro', dark: true, palette: dark, art: 'noite-quadra' },
  {
    id: 'noite-quadra',
    name: 'Noite na quadra',
    dark: true,
    palette: noiteQuadra,
    art: 'noite-quadra',
  },
  {
    id: 'golden-hour',
    name: 'Fim de tarde',
    dark: true,
    palette: goldenHour,
    art: 'golden-hour',
  },
  {
    id: 'dia-de-jogo',
    name: 'Dia de jogo',
    dark: false,
    palette: diaDeJogo,
    art: 'dia-de-jogo',
  },
  {
    id: 'ceu-vermelho',
    name: 'Céu vermelho',
    dark: true,
    palette: ceuVermelho,
    art: 'ceu-vermelho',
  },
  {
    id: 'ceu-claro',
    name: 'Céu claro',
    dark: false,
    palette: ceuClaro,
    art: 'ceu-claro',
  },
];

export function isThemeId(value: unknown): value is ThemeId {
  return typeof value === 'string' && themes.some((theme) => theme.id === value);
}

/** Fallback tolerante: id desconhecido cai no tema claro. */
export function themeById(id: string): Theme {
  return themes.find((theme) => theme.id === id) ?? themes[0];
}

function channelLuminance(channel: number): number {
  const value = channel / 255;
  return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
}

function relativeLuminance(hex: string): number {
  const value = hex.replace('#', '');
  const full =
    value.length === 3
      ? value
          .split('')
          .map((char) => `${char}${char}`)
          .join('')
      : value;
  if (!/^[0-9a-f]{6}$/i.test(full)) {
    throw new Error(`Cor inválida: ${hex}`);
  }
  const [red, green, blue] = [0, 2, 4].map((offset) =>
    channelLuminance(parseInt(full.slice(offset, offset + 2), 16)),
  );
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
}

/** Razão de contraste WCAG 2.x entre duas cores hex, arredondada em 2 casas. */
export function contrastRatio(foreground: string, background: string): number {
  const first = relativeLuminance(foreground);
  const second = relativeLuminance(background);
  const [lighter, darker] = first > second ? [first, second] : [second, first];
  return Math.round(((lighter + 0.05) / (darker + 0.05)) * 100) / 100;
}
