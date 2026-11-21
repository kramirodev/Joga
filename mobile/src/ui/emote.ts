import type { VisualCatalog, VisualItem } from '../api/types';

import type { IconName } from './icon-data';

/**
 * Emote no chat: o `body` continua texto puro, então o emote viaja como token
 * curto `[emote:<chave-do-catálogo>]`. Este módulo é puro (sem React Native e
 * sem imports de runtime) para poder ser testado direto pelo Node.
 */

/** Limite de emotes resolvidos por mensagem; o excedente continua literal. */
export const EMOTE_TOKEN_LIMIT = 20;

/** Mesmo marcador de `LOCAL_VISUAL_CATALOG` em `identity.ts`. */
const LOCAL_CATALOG_VERSION = 'local-1';

const TOKEN_PATTERN = /\[emote:([A-Za-z0-9][A-Za-z0-9._-]{0,63})\]/g;

export type EmoteSegment =
  | { type: 'text'; text: string }
  | { type: 'emote'; key: string; name: string; icon: IconName | null; raw: string };

function catalogIsLocal(catalog: VisualCatalog): boolean {
  const version = catalog.version ?? catalog.catalog_version;
  return version === LOCAL_CATALOG_VERSION;
}

/** Emotes que o app pode oferecer: catálogo do servidor, `kind='emote'`, `free`. */
export function chatEmoteOptions(catalog: VisualCatalog): VisualItem[] {
  if (catalogIsLocal(catalog)) {
    return [];
  }
  return catalog.items.filter(
    (item) => item.kind === 'emote' && item.active !== false && item.unlock_state === 'free',
  );
}

/** Corpo enviado no `POST` de mensagem; nunca é digitado no composer. */
export function emoteToken(key: string): string {
  return `[emote:${key}]`;
}

/**
 * Só usamos ícone quando o catálogo declara um ícone local (`icon:*`). Artwork
 * SVG do emote não é carregado pelo app, então `emotes/emote-joinha.svg` cai no
 * nome em texto — nunca em um ícone aleatório.
 */
export function emoteIcon(item: VisualItem): IconName | null {
  const ref = item.asset_ref ?? '';
  if (!/^icon:/i.test(ref)) {
    return null;
  }
  const name = ref.slice(ref.indexOf(':') + 1).toLowerCase();
  return /^[a-z0-9-]+$/.test(name) ? (name as IconName) : null;
}

/** Emote ativo do catálogo; qualquer outro `kind`/chave é tratado como texto. */
export function catalogEmote(catalog: VisualCatalog, key: string): VisualItem | null {
  return (
    catalog.items.find(
      (item) => item.key === key && item.kind === 'emote' && item.active !== false,
    ) ?? null
  );
}

/**
 * Separa texto e emotes. Token desconhecido, chave fora do catálogo, catálogo
 * local/ausente ou excedente do limite continuam no texto literal.
 */
export function parseEmoteBody(body: string, catalog: VisualCatalog): EmoteSegment[] {
  if (!body) {
    return [];
  }
  if (catalogIsLocal(catalog)) {
    return [{ type: 'text', text: body }];
  }
  const segments: EmoteSegment[] = [];
  let cursor = 0;
  let resolved = 0;
  TOKEN_PATTERN.lastIndex = 0;
  let match: RegExpExecArray | null = TOKEN_PATTERN.exec(body);
  while (match) {
    const item = resolved < EMOTE_TOKEN_LIMIT ? catalogEmote(catalog, match[1]) : null;
    if (!item) {
      match = TOKEN_PATTERN.exec(body);
      continue;
    }
    if (match.index > cursor) {
      segments.push({ type: 'text', text: body.slice(cursor, match.index) });
    }
    segments.push({
      type: 'emote',
      key: item.key,
      name: item.name,
      icon: emoteIcon(item),
      raw: match[0],
    });
    resolved += 1;
    cursor = match.index + match[0].length;
    match = TOKEN_PATTERN.exec(body);
  }
  if (cursor < body.length) {
    segments.push({ type: 'text', text: body.slice(cursor) });
  }
  return segments;
}

/** Texto falado da mensagem: emote vira o nome, sem expor o token. */
export function emoteSpokenText(segments: EmoteSegment[]): string {
  return segments
    .map((segment) => (segment.type === 'emote' ? `Emote ${segment.name}` : segment.text))
    .join('');
}

/** `true` quando a bolha tem só um emote (permite o formato compacto). */
export function isEmoteOnly(segments: EmoteSegment[]): boolean {
  return segments.length === 1 && segments[0].type === 'emote';
}
