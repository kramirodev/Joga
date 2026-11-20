export type Palette = {
  bg: string;
  surface: string;
  surface2: string;
  surface3: string;
  ink: string;
  inkSoft: string;
  muted: string;
  line: string;
  lineStrong: string;
  lime: string;
  limeDeep: string;
  limeSoft: string;
  blue: string;
  blueSoft: string;
  green: string;
  greenSoft: string;
  orange: string;
  orangeSoft: string;
  red: string;
  redSoft: string;
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
  line: '#D5D9D6',
  lineStrong: '#D5D9D6',
  lime: '#E53935',
  limeDeep: '#E53935',
  limeSoft: '#E7EAE7',
  blue: '#62686E',
  blueSoft: '#E7EAE7',
  green: '#62686E',
  greenSoft: '#E7EAE7',
  orange: '#E53935',
  orangeSoft: '#E7EAE7',
  red: '#62686E',
  redSoft: '#E7EAE7',
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
  bg: '#15171A',
  surface: '#1E2125',
  surface2: '#292D32',
  surface3: '#292D32',
  ink: '#F1F3F0',
  inkSoft: '#A6ABB1',
  muted: '#A6ABB1',
  line: '#383D43',
  lineStrong: '#383D43',
  lime: '#E53935',
  limeDeep: '#E53935',
  limeSoft: '#292D32',
  blue: '#A6ABB1',
  blueSoft: '#292D32',
  green: '#A6ABB1',
  greenSoft: '#292D32',
  orange: '#E53935',
  orangeSoft: '#292D32',
  red: '#E53935',
  redSoft: '#292D32',
  onInk: '#F1F3F0',
  softOnInk: '#A6ABB1',
  lineOnInk: '#383D43',
  heat1: '#1E2125',
  heat2: '#292D32',
  heat3: '#A6ABB1',
  heat4: '#E53935',
  progressTrack: '#383D43',
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
