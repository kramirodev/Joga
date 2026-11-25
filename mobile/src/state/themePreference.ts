import * as SecureStore from 'expo-secure-store';

import { isThemeId, type ThemeId } from '../ui/themes';

export const THEME_KEY = 'joga.theme';

/** Leitura tolerante: aparelho sem SecureStore ou valor inválido cai no sistema. */
export async function loadThemeId(): Promise<ThemeId | null> {
  try {
    const raw = await SecureStore.getItemAsync(THEME_KEY);
    return raw && isThemeId(raw) ? raw : null;
  } catch {
    return null;
  }
}

/** Falha ao gravar não bloqueia a troca: o tema continua válido em memória. */
export async function saveThemeId(themeId: ThemeId): Promise<void> {
  try {
    await SecureStore.setItemAsync(THEME_KEY, themeId);
  } catch {
    // Preferência local apenas; a troca de tema não depende de persistência.
  }
}
