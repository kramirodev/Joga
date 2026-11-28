/**
 * Telas de perfil em que a partida encontrada tem precedência. Inclui o perfil
 * próprio, o público (o "olhinho") e as edições que saem deles; um lobby
 * esperando não pode ficar escondido atrás do perfil.
 */
export const PROFILE_SURFACE_IDS = [
  'profile-me',
  'profile-other',
  'profile-edit',
  'identity-editor',
  'avatar-editor',
  'sports',
  'availability',
  'region',
  'region-cep-locked',
] as const;

const PROFILE_SURFACES: ReadonlySet<string> = new Set(PROFILE_SURFACE_IDS);

export function isProfileSurface(screenId: string): boolean {
  return PROFILE_SURFACES.has(screenId);
}

export type QueueMatchTarget = {
  screen: 'lobby-found';
  params: { lobbyId: string; mode: string };
};

/** Só o que a regra precisa da entrada `matched` do servidor. */
export type MatchedQueueEntry = {
  mode: string;
  lobby: { id: string } | null;
};

/**
 * Decide se a partida encontrada deve levar o usuário ao lobby, mesmo fora das
 * telas de fila. A regra é pura e idempotente: `handledLobbyId` garante que o
 * mesmo lobby navega uma única vez — voltar ao perfil não puxa o usuário de
 * novo e um lobby novo volta a ter precedência.
 */
export function queueMatchDestination(
  currentScreenId: string,
  matched: MatchedQueueEntry | null | undefined,
  handledLobbyId: string | null,
): QueueMatchTarget | null {
  if (!matched?.lobby) {
    return null;
  }
  if (handledLobbyId === matched.lobby.id) {
    return null;
  }
  if (!isProfileSurface(currentScreenId)) {
    return null;
  }
  return {
    screen: 'lobby-found',
    params: { lobbyId: matched.lobby.id, mode: matched.mode },
  };
}
