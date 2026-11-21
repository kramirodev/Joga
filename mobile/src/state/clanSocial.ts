import type { ClanJoinPolicy, ClanMessage } from '../api/types';

/**
 * Regras puras de clã compartilhadas pelas telas sociais.
 *
 * Ficam fora do componente para poderem ser testadas sem React Native:
 * tag sempre com `#`, política legível (open/approval/closed) e a ordem do
 * chat (antigas acima, novas abaixo) com reconciliação por `id` do servidor.
 */

export type ClanRole = 'owner' | 'admin' | 'member';

export type ChatRowStatus = 'sent' | 'sending' | 'failed';

export type ChatRow = {
  /** Chave estável da lista: id do servidor ou id temporário do envio. */
  key: string;
  serverId: string | null;
  senderId: string;
  displayName: string | null;
  body: string;
  createdAt: string;
  status: ChatRowStatus;
  /** Motivo curto e acionável quando o envio falha (sessão, rede, limite). */
  errorText?: string;
};

const TAG_MAX = 7;
const TAG_MIN = 2;

/** Só `[A-Z0-9]`, em maiúsculas, no máximo 7 caracteres (miolo sem `#`). */
export function normalizeTagInput(raw: string): string {
  return raw
    .toUpperCase()
    .replace(/#/g, '')
    .replace(/[^A-Z0-9]/g, '')
    .slice(0, TAG_MAX);
}

/** O backend faz `strip().upper()` e aceita 2–8 com `#`. */
export function tagPayload(core: string): string {
  return `#${normalizeTagInput(core)}`;
}

export function tagIsValid(core: string): boolean {
  return new RegExp(`^[A-Z0-9]{${TAG_MIN},${TAG_MAX}}$`).test(core);
}

/** Exibe sempre `#TAG`, inclusive para tags legadas gravadas sem `#`. */
export function displayClanTag(tag: string | null | undefined): string {
  const clean = (tag ?? '').trim();
  if (!clean) {
    return '#—';
  }
  return clean.startsWith('#') ? clean : `#${clean}`;
}

/** `approval` não é `closed`: a UI nunca deve achatar as duas políticas. */
export function joinPolicyLabel(policy: string | null | undefined): string {
  if (policy === 'open') {
    return 'Aberto';
  }
  if (policy === 'approval') {
    return 'Aprovação';
  }
  if (policy === 'closed') {
    return 'Fechado';
  }
  return 'Política desconhecida';
}

export function joinPolicyExplanation(policy: string | null | undefined): string {
  if (policy === 'open') {
    return 'Entrada imediata enquanto houver vaga.';
  }
  if (policy === 'approval') {
    return 'Entrada por aprovação de um oficial ou do dono.';
  }
  if (policy === 'closed') {
    return 'Este clã não aceita novas entradas.';
  }
  return 'Entrada não informada.';
}

/**
 * Nome legível de um membro. `display_name` pode vir nulo **ou vazio** do
 * servidor; para a própria linha, cai no nome do perfil e depois em "Jogador".
 */
export function memberDisplayName(
  member: { user_id: string; display_name: string | null },
  options?: { selfUserId?: string | null; selfProfileName?: string | null },
): string {
  const own = member.display_name?.trim();
  if (own) {
    return own;
  }
  const isSelf = !!options?.selfUserId && member.user_id === options.selfUserId;
  const profileName = isSelf ? options?.selfProfileName?.trim() : '';
  if (profileName) {
    return profileName;
  }
  return 'Jogador';
}

/** Só mensagens confirmadas pelo servidor podem ser denunciadas. */
export function isReportableMessage(row: {
  serverId: string | null;
  status: ChatRowStatus;
}): boolean {
  return row.status === 'sent' && !!row.serverId;
}

/** 409/duplicada significa que a denúncia já existia, não que falhou. */
export function isDuplicateReport(error: { status: number; code: string }): boolean {
  return error.status === 409 || /already|duplicate|reported/.test(error.code);
}

export function myRoleLabel(role: string | null | undefined): string {
  if (role === 'owner') {
    return 'Dono';
  }
  if (role === 'admin') {
    return 'Oficial';
  }
  return 'Membro';
}

export function isOwnerRole(role: string | null | undefined): boolean {
  return role === 'owner';
}

export function isAdminRole(role: string | null | undefined): boolean {
  return role === 'admin' || role === 'owner';
}

export type ClanDraft = {
  name: string;
  description: string;
  join_policy: string;
};

/**
 * Corpo do `PATCH /clans/{id}` a partir do rascunho e da base carregada.
 *
 * Só envia o que mudou (descrição vazia vira `null`) e **nunca** inclui `tag`:
 * a tag do clã é imutável por decisão de produto, não apenas por omissão da
 * tela. O tipo de retorno não tem o campo.
 */
export function clanUpdatePatch(
  baseline: ClanDraft,
  draft: ClanDraft,
): {
  name?: string;
  description?: string | null;
  join_policy?: ClanJoinPolicy;
} {
  const patch: {
    name?: string;
    description?: string | null;
    join_policy?: ClanJoinPolicy;
  } = {};
  const name = draft.name.trim();
  if (name && name !== baseline.name.trim()) {
    patch.name = name;
  }
  const description = draft.description.trim();
  if (description !== baseline.description.trim()) {
    patch.description = description.length > 0 ? description : null;
  }
  if (
    draft.join_policy !== baseline.join_policy &&
    (draft.join_policy === 'open' ||
      draft.join_policy === 'approval' ||
      draft.join_policy === 'closed')
  ) {
    patch.join_policy = draft.join_policy;
  }
  return patch;
}

/** Busca local de amigos: sem diferenciar maiúsculas nem acentos. */
export function normalizeSearchText(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim();
}

export function matchesSearch(name: string, query: string): boolean {
  const term = normalizeSearchText(query);
  return term.length === 0 || normalizeSearchText(name).includes(term);
}

/**
 * Validade de um convite recebido em texto curto. Devolve `null` quando a data
 * não vem ou é inválida, para a tela não inventar prazo.
 */
export function inviteExpiryLabel(
  expiresAt: string | null | undefined,
  now: Date = new Date(),
): string | null {
  if (!expiresAt) {
    return null;
  }
  const end = Date.parse(expiresAt);
  if (!Number.isFinite(end)) {
    return null;
  }
  const diff = end - now.getTime();
  if (diff <= 0) {
    return 'Este convite expirou.';
  }
  if (diff < 86_400_000) {
    return 'Expira em menos de 1 dia.';
  }
  const days = Math.floor(diff / 86_400_000);
  return days === 1 ? 'Expira em 1 dia.' : `Expira em ${days} dias.`;
}

function roleOrder(role: string): number {
  if (role === 'owner') {
    return 0;
  }
  if (role === 'admin') {
    return 1;
  }
  return 2;
}

/** Dono → oficiais → membros, com ordem estável por nome. */
export function sortMembers<
  T extends { role: string; display_name: string | null; user_id: string },
>(members: T[]): T[] {
  return [...members].sort((left, right) => {
    const byRole = roleOrder(left.role) - roleOrder(right.role);
    if (byRole !== 0) {
      return byRole;
    }
    const byName = (left.display_name ?? '').localeCompare(right.display_name ?? '');
    return byName !== 0 ? byName : left.user_id.localeCompare(right.user_id);
  });
}

function timestamp(value: string): number {
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function compareRows(left: ChatRow, right: ChatRow): number {
  const byTime = timestamp(left.createdAt) - timestamp(right.createdAt);
  return byTime !== 0 ? byTime : left.key.localeCompare(right.key);
}

export function chatRowFromMessage(message: ClanMessage): ChatRow {
  return {
    key: message.id,
    serverId: message.id,
    senderId: message.sender_id,
    displayName: message.display_name,
    body: message.body,
    createdAt: message.created_at,
    status: 'sent',
  };
}

/**
 * Junta a lista do servidor (que chega da mais nova para a mais antiga) com as
 * bolhas locais ainda não confirmadas. Mensagens com o mesmo `id` do servidor
 * não duplicam; a ordem final é cronológica.
 */
export function mergeChatRows(server: ClanMessage[], local: ChatRow[]): ChatRow[] {
  const serverIds = new Set(server.map((message) => message.id));
  const pending = local.filter((row) => (row.serverId ? !serverIds.has(row.serverId) : true));
  return [...server.map(chatRowFromMessage), ...pending].sort(compareRows);
}
