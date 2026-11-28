import { isThemeId, type ThemeId } from '../ui/themes.ts';

/**
 * Decisão de sincronização entre o tema salvo no aparelho (`SecureStore`) e o
 * `theme_id` de `GET /me/profile`. Função pura: o efeito (aplicar sem PUT ou
 * enviar com PUT) fica em `app.tsx`, o que mantém o caminho do servidor sem
 * risco de disparar outro PUT e entrar em loop.
 */
export type ThemeSyncDecision =
  { kind: 'apply'; themeId: ThemeId } | { kind: 'upload'; themeId: ThemeId } | { kind: 'keep' };

export type ThemeSyncInput = {
  /** `theme_id` do perfil; `null` quando o usuário ainda não escolheu. */
  serverThemeId: string | null | undefined;
  /** Tema salvo no aparelho, já validado ou não. */
  localThemeId: string | null | undefined;
  /** PUT anterior falhou e a troca local ainda não chegou ao servidor. */
  pendingUpload?: boolean;
};

/**
 * Política:
 * - alteração local pendente é reenviada (senão a próxima carga a perderia);
 * - tema conhecido no servidor vence e é aplicado localmente **sem** PUT;
 * - servidor nulo/ausente e tema local conhecido: primeira sincronização, envia
 *   o local;
 * - ID desconhecido no servidor não é sobrescrito: um build futuro pode ter
 *   temas novos e este app não deve apagar a escolha por não renderizá-la;
 * - sem nada válido, mantém o fallback local (claro/escuro do sistema).
 */
export function decideThemeSync({
  serverThemeId,
  localThemeId,
  pendingUpload = false,
}: ThemeSyncInput): ThemeSyncDecision {
  const local = isThemeId(localThemeId) ? localThemeId : null;

  if (pendingUpload && local) {
    return { kind: 'upload', themeId: local };
  }

  if (isThemeId(serverThemeId)) {
    return { kind: 'apply', themeId: serverThemeId };
  }

  if (!serverThemeId && local) {
    return { kind: 'upload', themeId: local };
  }

  return { kind: 'keep' };
}
