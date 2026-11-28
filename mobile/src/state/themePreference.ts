import * as SecureStore from 'expo-secure-store';

import { isThemeId, type ThemeId } from '../ui/themes';

export const THEME_KEY = 'joga.theme';

/**
 * Marca que o último PUT `/me/theme` falhou. Sem ela, a próxima carga do perfil
 * aplicaria o valor antigo do servidor e descartaria a troca feita offline.
 */
export const THEME_PENDING_KEY = 'joga.theme.pending';

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

/** Leitura tolerante da pendência de envio; ausência da chave significa sincronizado. */
export async function loadThemeUploadPending(): Promise<boolean> {
  try {
    return (await SecureStore.getItemAsync(THEME_PENDING_KEY)) === '1';
  } catch {
    return false;
  }
}

/** Gravação best-effort: sem a marca, a próxima carga ainda envia o tema local. */
export async function saveThemeUploadPending(pending: boolean): Promise<void> {
  try {
    if (pending) {
      await SecureStore.setItemAsync(THEME_PENDING_KEY, '1');
    } else {
      await SecureStore.deleteItemAsync(THEME_PENDING_KEY);
    }
  } catch {
    // Sem persistência a sincronização continua tentando na próxima carga.
  }
}
