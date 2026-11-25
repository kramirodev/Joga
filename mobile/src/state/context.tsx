import { createContext, useContext } from 'react';

import { dark, light, type Palette } from '../ui/theme';
import type { ThemeId } from '../ui/themes';

export type TabKey = 'jogar' | 'partidas' | 'temporada' | 'social' | 'perfil';

export type Params = Record<string, string | number | boolean | null | undefined>;

export type NavValue = {
  id: string;
  tab: TabKey;
  params: Params;
  canGoBack: boolean;
  go: (id: string, params?: Params) => void;
  replace: (id: string, params?: Params) => void;
  reset: (id: string, params?: Params) => void;
  back: () => void;
  tabTo: (tab: TabKey) => void;
  openModal: (id: string, onConfirm?: () => void) => void;
  toast: (message: string) => void;
};

export const NavContext = createContext<NavValue | null>(null);

export function useNav(): NavValue {
  const value = useContext(NavContext);
  if (!value) {
    throw new Error('useNav fora do provider');
  }
  return value;
}

export type ThemeValue = {
  /** Id do tema escolhido (claro, escuro ou uma das artes). */
  themeId: ThemeId;
  setTheme: (themeId: ThemeId) => void;
  /** Paleta completa do tema escolhido. */
  palette: Palette;
  dark: boolean;
  setDark: (value: boolean) => void;
  fontScale: number;
  largeTargets: boolean;
  /**
   * Preferência efetiva de movimento: a interna (`accessibility.reducedMotion`)
   * combinada com `AccessibilityInfo.isReduceMotionEnabled()`. Publicada pelo
   * `Shell` para que qualquer componente saiba se pode animar.
   */
  reducedMotion: boolean;
  /**
   * Espaço que o conteúdo precisa reservar no rodapé para não ficar sob a barra
   * de navegação do sistema. Calculado uma única vez no `Shell`:
   * `0` quando a tab bar está visível (ela já consome o inset) e
   * `insets.bottom` quando não está. Telas nunca chamam `useSafeAreaInsets`
   * diretamente; sheets/modais no nível do `Shell` usam o inset bruto.
   */
  contentBottomInset: number;
};

export const ThemeContext = createContext<ThemeValue>({
  themeId: 'claro',
  setTheme: () => undefined,
  palette: light,
  dark: false,
  setDark: () => undefined,
  fontScale: 1,
  largeTargets: false,
  reducedMotion: false,
  contentBottomInset: 0,
});

export function useTheme(): ThemeValue {
  return useContext(ThemeContext);
}

export const palettes = { light, dark };
