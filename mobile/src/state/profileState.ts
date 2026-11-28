/**
 * Regras puras do perfil: tag canônica, clã, visibilidade do perfil público e
 * destinos do toque no avatar.
 *
 * A autorização continua no servidor. Aqui só traduzimos o que o contrato já
 * devolve (`profile.tag`, `clan`, `relation`) para texto e ações da tela.
 */

import type { Badge, PublicPlayer, VisualIdentity } from '../api/types';

export type PublicProfileStatus =
  'self' | 'friend' | 'incoming_request' | 'outgoing_request' | 'public';

/** Remove `#`, espaços e caixa; a tag do servidor já vem no formato canônico. */
export function normalizeProfileTag(tag: string | null | undefined): string {
  return (tag ?? '').replace(/#/g, '').replace(/\s+/g, '').trim().toUpperCase();
}

/** Tag pronta para exibição, sem duplicar `#`; ausência vira travessão. */
export function profileTagLabel(tag: string | null | undefined): string {
  const bare = normalizeProfileTag(tag);
  return bare ? `#${bare}` : '—';
}

/** O cartão já imprime `#`; recebe apenas os caracteres da tag. */
export function profileTagForCard(tag: string | null | undefined): string {
  return normalizeProfileTag(tag) || '—';
}

/**
 * Nome do clã no primeiro frame. Sem clã só é "Sem clã" depois que a carga
 * terminou; antes disso mostramos travessão para não afirmar algo falso.
 */
export function profileClanName(name: string | null | undefined, loaded: boolean): string {
  const clean = (name ?? '').trim();
  if (clean) {
    return clean;
  }
  return loaded ? 'Sem clã' : '—';
}

/** Estado do perfil público derivado do próprio usuário e da relação do servidor. */
export function publicProfileStatus(
  isSelf: boolean,
  relation: string | null | undefined,
): PublicProfileStatus {
  if (isSelf) {
    return 'self';
  }
  switch (relation) {
    case 'friend':
      return 'friend';
    case 'incoming_request':
      return 'incoming_request';
    case 'outgoing_request':
      return 'outgoing_request';
    default:
      return 'public';
  }
}

/** Só o perfil de outra pessoa sem vínculo oferece "Adicionar amigo". */
export function canRequestFriendship(
  isSelf: boolean,
  relation: string | null | undefined,
): boolean {
  return !isSelf && (relation ?? 'none') === 'none';
}

export function publicProfileStatusLabel(status: PublicProfileStatus): string {
  switch (status) {
    case 'self':
      return 'VOCÊ';
    case 'friend':
      return 'AMIGO';
    case 'incoming_request':
      return 'PEDIDO RECEBIDO';
    case 'outgoing_request':
      return 'PEDIDO ENVIADO';
    default:
      return 'PERFIL PÚBLICO';
  }
}

/** Pré-preenchimento da busca de amigos, sem inventar nome nem tag. */
export function friendSearchPrefill(
  name: string | null | undefined,
  tag: string | null | undefined,
): { name: string; tag: string } {
  return { name: (name ?? '').trim(), tag: normalizeProfileTag(tag) };
}

export type AvatarTarget = 'profile-edit' | 'profile-other' | 'identity-editor' | null;

/** Toque no avatar: edita o próprio perfil e abre a identidade dentro da edição. */
export function avatarTargetFor(screen: 'me' | 'edit' | 'other'): AvatarTarget {
  if (screen === 'me') {
    return 'profile-edit';
  }
  if (screen === 'edit') {
    return 'identity-editor';
  }
  return null;
}

export type PublicCardFields = {
  tier: string | null;
  level: number | null;
  qualifier: string | null;
  seasonLabel: string | null;
  record: number | null;
  winstreak: number | null;
  badges: string[];
  visual: Partial<VisualIdentity> | null;
  themeId: string | null;
};

const EMPTY_PUBLIC_CARD: PublicCardFields = {
  tier: null,
  level: null,
  qualifier: null,
  seasonLabel: null,
  record: null,
  winstreak: null,
  badges: [],
  visual: null,
  themeId: null,
};

/**
 * Traduz o snapshot público para os campos do `ProfileCard`. Ausência continua
 * ausência: nada aqui preenche tier, nível, recorde ou badge por conta própria.
 */
export function publicCardFields(player: PublicPlayer | null | undefined): PublicCardFields {
  const card = player?.card;
  if (!card) {
    return { ...EMPTY_PUBLIC_CARD, badges: [] };
  }
  return {
    tier: card.tier ?? null,
    level: card.level ?? null,
    qualifier: card.qualifier ?? null,
    seasonLabel: card.season_label ?? null,
    record: card.record ?? null,
    winstreak: card.win_streak ?? null,
    badges: (card.badges ?? []).slice(0, 3).map((badge) => badge.name),
    visual: card.visual ?? null,
    themeId: card.theme_id ?? null,
  };
}

/** Insígnias dos quadros do cartão: só as equipadas, na ordem dos slots. */
export function equippedBadges(badges: Badge[] | null | undefined): Badge[] {
  return (badges ?? [])
    .filter((badge) => badge.equipped_slot != null)
    .sort((first, second) => (first.equipped_slot ?? 0) - (second.equipped_slot ?? 0))
    .slice(0, 3);
}

/** Nomes das insígnias equipadas, para os três quadros do cartão. */
export function equippedBadgeNames(badges: Badge[] | null | undefined): string[] {
  return equippedBadges(badges).map((badge) => badge.name);
}
