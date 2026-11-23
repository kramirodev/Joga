export type Palette = {
  bg: string;
  surface: string;
  surface2: string;
  surface3: string;
  ink: string;
  inkSoft: string;
  muted: string;
  subtle: string;
  line: string;
  lineSubtle: string;
  lineStrong: string;
  lime: string;
  limeDeep: string;
  limeSoft: string;
  /**
   * Papel de marca. `lime` é o nome legado usado pelas telas; `brand` existe
   * para o tema escuro falar a mesma língua da documentação e do teste de
   * contraste. Os dois carregam o mesmo valor — não são um tema novo.
   */
  brand: string;
  brandStrong: string;
  brandInk: string;
  focus: string;
  blue: string;
  blueSoft: string;
  green: string;
  greenSoft: string;
  orange: string;
  orangeSoft: string;
  red: string;
  redSoft: string;
  success: string;
  warning: string;
  danger: string;
  info: string;
  onInk: string;
  softOnInk: string;
  lineOnInk: string;
  heat1: string;
  heat2: string;
  heat3: string;
  heat4: string;
  progressTrack: string;
};

export const light: Palette = {
  bg: '#F1F3F0',
  surface: '#FFFFFF',
  surface2: '#E7EAE7',
  surface3: '#E7EAE7',
  ink: '#17191B',
  inkSoft: '#62686E',
  muted: '#62686E',
  subtle: '#A6ABB1',
  line: '#D5D9D6',
  lineSubtle: '#D5D9D6',
  lineStrong: '#D5D9D6',
  lime: '#E53935',
  limeDeep: '#E53935',
  limeSoft: '#E7EAE7',
  brand: '#E53935',
  brandStrong: '#E53935',
  brandInk: '#F1F3F0',
  focus: '#E53935',
  blue: '#62686E',
  blueSoft: '#E7EAE7',
  green: '#62686E',
  greenSoft: '#E7EAE7',
  orange: '#E53935',
  orangeSoft: '#E7EAE7',
  red: '#62686E',
  redSoft: '#E7EAE7',
  success: '#62686E',
  warning: '#62686E',
  danger: '#62686E',
  info: '#62686E',
  onInk: '#F1F3F0',
  softOnInk: '#A6ABB1',
  lineOnInk: '#383D43',
  heat1: '#E7EAE7',
  heat2: '#D5D9D6',
  heat3: '#A6ABB1',
  heat4: '#E53935',
  progressTrack: '#D5D9D6',
};

export const dark: Palette = {
  bg: '#0A0B0D',
  surface: '#131417',
  surface2: '#191A1E',
  surface3: '#222327',
  ink: '#F4F2EE',
  inkSoft: '#8E8E8E',
  muted: '#A6A6A6',
  subtle: '#8E8E8E',
  line: '#2A2B2F',
  lineSubtle: '#414349',
  lineStrong: '#6E7077',
  lime: '#F03B3B',
  limeDeep: '#FF5C5C',
  limeSoft: '#222327',
  brand: '#F03B3B',
  brandStrong: '#FF5C5C',
  brandInk: '#140404',
  focus: '#FF5C5C',
  blue: '#8EC8FF',
  blueSoft: '#191A1E',
  green: '#79D8BF',
  greenSoft: '#191A1E',
  orange: '#FFCF72',
  orangeSoft: '#191A1E',
  red: '#FF8F7F',
  redSoft: '#191A1E',
  success: '#79D8BF',
  warning: '#FFCF72',
  danger: '#FF8F7F',
  info: '#8EC8FF',
  onInk: '#F4F2EE',
  softOnInk: '#A6A6A6',
  lineOnInk: '#414349',
  heat1: '#131417',
  heat2: '#191A1E',
  heat3: '#A6A6A6',
  heat4: '#F03B3B',
  progressTrack: '#222327',
};

export const space = {
  screenX: 16,
  gap: 14,
  card: 16,
  radius: 18,
  radiusSm: 10,
  tabBar: 76,
  tap: 46,
};

export type TextVariant =
  | 'display'
  | 'h1'
  | 'h1xl'
  | 'h2'
  | 'h3'
  | 'lead'
  | 'sub'
  | 'tiny'
  | 'label'
  | 'num'
  | 'topbarTitle'
  | 'topbarSub';

export const type: Record<
  TextVariant,
  {
    fontSize: number;
    lineHeight: number;
    letterSpacing: number;
    fontWeight: '400' | '600' | '700' | '800' | '900';
    uppercase: boolean;
  }
> = {
  display: { fontSize: 32, lineHeight: 31, letterSpacing: -1, fontWeight: '900', uppercase: true },
  h1: { fontSize: 30, lineHeight: 29, letterSpacing: -0.9, fontWeight: '900', uppercase: true },
  h1xl: { fontSize: 38, lineHeight: 36, letterSpacing: -1.1, fontWeight: '900', uppercase: true },
  h2: { fontSize: 20, lineHeight: 21, letterSpacing: -0.2, fontWeight: '900', uppercase: true },
  h3: { fontSize: 15, lineHeight: 18, letterSpacing: 0.4, fontWeight: '800', uppercase: true },
  lead: { fontSize: 15, lineHeight: 22.5, letterSpacing: 0, fontWeight: '400', uppercase: false },
  sub: { fontSize: 14, lineHeight: 21, letterSpacing: 0, fontWeight: '400', uppercase: false },
  tiny: { fontSize: 14, lineHeight: 19.6, letterSpacing: 0, fontWeight: '400', uppercase: false },
  label: { fontSize: 11, lineHeight: 15.5, letterSpacing: 1.5, fontWeight: '800', uppercase: true },
  num: { fontSize: 24, lineHeight: 27, letterSpacing: -0.7, fontWeight: '900', uppercase: false },
  topbarTitle: {
    fontSize: 16,
    lineHeight: 18,
    letterSpacing: 0.4,
    fontWeight: '900',
    uppercase: true,
  },
  topbarSub: {
    fontSize: 13,
    lineHeight: 18,
    letterSpacing: 0,
    fontWeight: '400',
    uppercase: false,
  },
};
