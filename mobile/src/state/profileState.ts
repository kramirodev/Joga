/**
 * Regras puras do perfil: tag canônica, clã, visibilidade do perfil público e
 * destinos do toque no avatar.
 *
 * A autorização continua no servidor. Aqui só traduzimos o que o contrato já
 * devolve (`profile.tag`, `clan`, `relation`) para texto e ações da tela.
 */

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

export type AvatarTarget = 'profile-other' | 'identity-editor' | null;

/** Toque no avatar: perfil público no próprio perfil e identidade na edição. */
export function avatarTargetFor(screen: 'me' | 'edit' | 'other'): AvatarTarget {
  if (screen === 'me') {
    return 'profile-other';
  }
  if (screen === 'edit') {
    return 'identity-editor';
  }
  return null;
}
