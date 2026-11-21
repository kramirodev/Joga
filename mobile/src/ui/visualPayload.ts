import type {
  VisualCatalog,
  VisualIdentity,
  VisualIdentityResponse,
  VisualKind,
} from '../api/types';

/**
 * Montagem pura do corpo de `PUT /me/visual`.
 *
 * O servidor valida **os seis** slots. O editor do app só altera ícone,
 * moldura, destaque e selo; `entry`/`emote` não têm editor e precisam manter
 * exatamente a chave que o servidor confirmou em `GET /me/visual`.
 */

type IdentityKeyField =
  'icon_key' | 'frame_key' | 'accent_key' | 'entry_key' | 'emote_key' | 'badge_key';

const IDENTITY_KEY_FIELD: Record<VisualKind, IdentityKeyField> = {
  icon: 'icon_key',
  frame: 'frame_key',
  accent: 'accent_key',
  entry: 'entry_key',
  emote: 'emote_key',
  badge: 'badge_key',
};

export type VisualPayload = Omit<VisualIdentity, 'catalog_version'>;

/** Chaves confirmadas pelo servidor (podem não existir no catálogo local). */
export function confirmedVisualKeys(
  input: Partial<VisualIdentityResponse> | Partial<VisualIdentity> | null | undefined,
): Partial<Record<VisualKind, string>> | null {
  if (!input) {
    return null;
  }
  const source = input as Record<string, unknown>;
  const keys: Partial<Record<VisualKind, string>> = {};
  for (const kind of Object.keys(IDENTITY_KEY_FIELD) as VisualKind[]) {
    const value = source[IDENTITY_KEY_FIELD[kind]];
    if (typeof value === 'string' && value.length > 0) {
      keys[kind] = value;
    }
  }
  return Object.keys(keys).length > 0 ? keys : null;
}

function itemOf(catalog: VisualCatalog, key: string, kind: VisualKind) {
  return (
    catalog.items.find((item) => item.key === key && item.kind === kind && item.active !== false) ??
    null
  );
}

function firstOf(catalog: VisualCatalog, kind: VisualKind) {
  return catalog.items.find((item) => item.kind === kind && item.active !== false) ?? null;
}

export function buildVisualPayload({
  identity,
  catalog,
  confirmed,
  localOnly,
}: {
  identity: VisualIdentity;
  catalog: VisualCatalog;
  confirmed?: Partial<VisualIdentityResponse> | Partial<VisualIdentity> | null;
  /** `true` quando o catálogo é o fallback local: nunca envia PUT. */
  localOnly: boolean;
}): VisualPayload | null {
  if (localOnly) {
    return null;
  }
  const confirmedKeys = confirmedVisualKeys(confirmed);
  // Sem `GET /me/visual` o app não conhece entry/emote atuais. Um PUT com os
  // seis slots apagaria esses valores; melhor manter tudo local e avisar.
  if (!confirmedKeys) {
    return null;
  }

  const resolve = (kind: VisualKind, editable: boolean): string | null => {
    if (!editable && confirmedKeys?.[kind]) {
      return confirmedKeys[kind] ?? null;
    }
    const current = itemOf(catalog, identity[IDENTITY_KEY_FIELD[kind]], kind);
    if (current) {
      return current.key;
    }
    if (confirmedKeys?.[kind]) {
      return confirmedKeys[kind] ?? null;
    }
    return firstOf(catalog, kind)?.key ?? null;
  };

  const payload: VisualPayload = {
    icon_key: resolve('icon', true) ?? '',
    frame_key: resolve('frame', true) ?? '',
    accent_key: resolve('accent', true) ?? '',
    entry_key: resolve('entry', false) ?? '',
    emote_key: resolve('emote', false) ?? '',
    badge_key: resolve('badge', true) ?? '',
  };
  if (Object.values(payload).some((key) => key.length === 0)) {
    return null;
  }
  return payload;
}
