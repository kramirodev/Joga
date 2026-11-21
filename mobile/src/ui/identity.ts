import type {
  VisualCatalog,
  VisualIdentity,
  VisualIdentityResponse,
  VisualItem,
  VisualKind,
} from '../api/types';

import { ICONS, type IconName } from './icon-data';
import { buildVisualPayload, type VisualPayload } from './visualPayload';

/**
 * Fallback local do contrato de identidade visual. É usado enquanto
 * `GET /catalog/visual` não responder; o backend pode substituir o catálogo
 * inteiro sem mudar o componente.
 */
export const DEFAULT_IDENTITY: VisualIdentity = {
  icon_key: 'icon:user',
  frame_key: 'frame:carbon',
  accent_key: 'accent:graphite',
  entry_key: 'entry:default',
  emote_key: 'emote:wave',
  badge_key: 'badge:none',
  catalog_version: 'local-1',
};

type Seed = {
  key: string;
  kind: VisualKind;
  name: string;
  asset_ref: string;
  unlock_state: VisualItem['unlock_state'];
};

const SEEDS: Seed[] = [
  { key: 'icon:user', kind: 'icon', name: 'Jogador', asset_ref: 'icon:user', unlock_state: 'free' },
  { key: 'icon:bolt', kind: 'icon', name: 'Raio', asset_ref: 'icon:bolt', unlock_state: 'free' },
  { key: 'icon:users', kind: 'icon', name: 'Time', asset_ref: 'icon:users', unlock_state: 'free' },
  {
    key: 'icon:trophy',
    kind: 'icon',
    name: 'Troféu',
    asset_ref: 'icon:trophy',
    unlock_state: 'free',
  },
  {
    key: 'icon:shield',
    kind: 'icon',
    name: 'Escudo',
    asset_ref: 'icon:shield',
    unlock_state: 'free',
  },
  { key: 'icon:medal', kind: 'icon', name: 'Medalha', asset_ref: 'icon:medal', unlock_state: 'xp' },
  { key: 'icon:clan', kind: 'icon', name: 'Clã', asset_ref: 'icon:clan', unlock_state: 'free' },
  { key: 'icon:globe', kind: 'icon', name: 'Globo', asset_ref: 'icon:globe', unlock_state: 'free' },
  { key: 'icon:pin', kind: 'icon', name: 'Quadra', asset_ref: 'icon:pin', unlock_state: 'free' },
  {
    key: 'icon:clock',
    kind: 'icon',
    name: 'Horário',
    asset_ref: 'icon:clock',
    unlock_state: 'free',
  },
  { key: 'icon:chat', kind: 'icon', name: 'Resenha', asset_ref: 'icon:chat', unlock_state: 'free' },
  { key: 'icon:home', kind: 'icon', name: 'Casa', asset_ref: 'icon:home', unlock_state: 'free' },
  {
    key: 'icon:wallet',
    kind: 'icon',
    name: 'Ingressos',
    asset_ref: 'icon:wallet',
    unlock_state: 'free',
  },
  {
    key: 'icon:bell',
    kind: 'icon',
    name: 'Alerta',
    asset_ref: 'icon:bell',
    unlock_state: 'free',
  },
  { key: 'icon:flame', kind: 'icon', name: 'Chama', asset_ref: 'icon:bolt', unlock_state: 'xp' },
  {
    key: 'icon:captain',
    kind: 'icon',
    name: 'Capitão',
    asset_ref: 'icon:shield',
    unlock_state: 'xp',
  },

  { key: 'frame:none', kind: 'frame', name: 'Sem moldura', asset_ref: '', unlock_state: 'free' },
  {
    key: 'frame:carbon',
    kind: 'frame',
    name: 'Carbono',
    asset_ref: '#17191B',
    unlock_state: 'free',
  },
  {
    key: 'frame:lime',
    kind: 'frame',
    name: 'Vermelha',
    asset_ref: '#E53935',
    unlock_state: 'free',
  },
  {
    key: 'frame:steel',
    kind: 'frame',
    name: 'Aço',
    asset_ref: '#62686E',
    unlock_state: 'free',
  },
  {
    key: 'frame:paper',
    kind: 'frame',
    name: 'Papel',
    asset_ref: '#D5D9D6',
    unlock_state: 'free',
  },

  {
    key: 'accent:graphite',
    kind: 'accent',
    name: 'Grafite',
    asset_ref: '#17191B',
    unlock_state: 'free',
  },
  {
    key: 'accent:lime',
    kind: 'accent',
    name: 'Vermelho',
    asset_ref: '#E53935',
    unlock_state: 'free',
  },
  {
    key: 'accent:steel',
    kind: 'accent',
    name: 'Aço',
    asset_ref: '#62686E',
    unlock_state: 'free',
  },
  {
    key: 'accent:sand',
    kind: 'accent',
    name: 'Areia',
    asset_ref: '#D5D9D6',
    unlock_state: 'free',
  },
  {
    key: 'accent:paper',
    kind: 'accent',
    name: 'Papel',
    asset_ref: '#F1F3F0',
    unlock_state: 'free',
  },

  {
    key: 'entry:default',
    kind: 'entry',
    name: 'Entrada padrão',
    asset_ref: 'icon:user',
    unlock_state: 'free',
  },
  {
    key: 'entry:fast',
    kind: 'entry',
    name: 'Entrada rápida',
    asset_ref: 'icon:bolt',
    unlock_state: 'xp',
  },
  {
    key: 'entry:night',
    kind: 'entry',
    name: 'Entrada noturna',
    asset_ref: 'icon:clock',
    unlock_state: 'pass',
  },

  {
    key: 'emote:wave',
    kind: 'emote',
    name: 'Aceno',
    asset_ref: 'icon:users',
    unlock_state: 'free',
  },
  {
    key: 'emote:fist',
    kind: 'emote',
    name: 'Valeu',
    asset_ref: 'icon:shield',
    unlock_state: 'free',
  },
  { key: 'emote:fire', kind: 'emote', name: 'Fogo', asset_ref: 'icon:bolt', unlock_state: 'xp' },

  { key: 'badge:none', kind: 'badge', name: 'Sem selo', asset_ref: '', unlock_state: 'free' },
  {
    key: 'badge:rookie',
    kind: 'badge',
    name: 'Estreante',
    asset_ref: 'icon:user',
    unlock_state: 'free',
  },
  {
    key: 'badge:captain',
    kind: 'badge',
    name: 'Capitão',
    asset_ref: 'icon:shield',
    unlock_state: 'xp',
  },
  {
    key: 'badge:founder',
    kind: 'badge',
    name: 'Fundador',
    asset_ref: 'icon:medal',
    unlock_state: 'pass',
  },
  {
    key: 'badge:season',
    kind: 'badge',
    name: 'Temporada',
    asset_ref: 'icon:trophy',
    unlock_state: 'xp',
  },
];

export const LOCAL_VISUAL_CATALOG: VisualCatalog = {
  version: 'local-1',
  items: SEEDS.map((item) => ({ ...item, active: true })),
};

export function visualItems(catalog: VisualCatalog, kind: VisualKind): VisualItem[] {
  return catalog.items.filter((item) => item.kind === kind && item.active !== false);
}

export function catalogVersionOf(catalog: VisualCatalog): string | number {
  return catalog.version ?? catalog.catalog_version ?? 'local';
}

export function visualItem(catalog: VisualCatalog, key: string | undefined): VisualItem | null {
  if (!key) {
    return null;
  }
  return catalog.items.find((item) => item.key === key) ?? null;
}

export function iconNameFromRef(ref: string | undefined, fallback: IconName = 'user'): IconName {
  const raw = (ref ?? '').toLowerCase();
  const cleaned = raw.replace(/^icon:/i, '');
  if (Object.prototype.hasOwnProperty.call(ICONS, cleaned)) {
    return cleaned as IconName;
  }
  if (raw.includes('escudo')) {
    return 'shield';
  }
  if (raw.includes('futebol') || raw.includes('futevolei')) {
    return 'bolt';
  }
  if (raw.includes('volei') || raw.includes('vôlei')) {
    return 'users';
  }
  if (raw.includes('trofeu') || raw.includes('trophy')) {
    return 'trophy';
  }
  if (raw.includes('medalha') || raw.includes('medal')) {
    return 'medal';
  }
  if (raw.includes('clan')) {
    return 'clan';
  }
  if (raw.includes('joinha') || raw.includes('emote')) {
    return 'users';
  }
  return fallback;
}

export function iconNameFor(
  catalog: VisualCatalog,
  key: string | undefined,
  fallback: IconName = 'user',
): IconName {
  const item = visualItem(catalog, key);
  return iconNameFromRef(item?.asset_ref ?? key, fallback);
}

export function itemColor(
  catalog: VisualCatalog,
  key: string | undefined,
  fallback: string,
): string {
  const item = visualItem(catalog, key);
  if (item?.asset_ref && /^#[0-9a-f]{3,8}$/i.test(item.asset_ref)) {
    return item.asset_ref;
  }
  const token = `${item?.key ?? ''} ${item?.asset_ref ?? ''}`.toLowerCase();
  if (token.includes('bronze')) {
    return '#A66B3D';
  }
  if (token.includes('prata') || token.includes('silver')) {
    return '#A6ABB1';
  }
  if (token.includes('ouro') || token.includes('gold')) {
    return '#E5B93C';
  }
  if (token.includes('lime')) {
    return '#E53935';
  }
  if (token.includes('azul')) {
    return '#3D6BFF';
  }
  if (token.includes('laranja')) {
    return '#F28C28';
  }
  if (token.includes('roxo')) {
    return '#8B5CF6';
  }
  if (token.includes('rosa')) {
    return '#E65C9C';
  }
  if (token.includes('ciano')) {
    return '#2DB7C4';
  }
  return fallback;
}

export function normalizeIdentity(
  input: Partial<VisualIdentityResponse> | Partial<VisualIdentity> | null | undefined,
  catalog: VisualCatalog = LOCAL_VISUAL_CATALOG,
): VisualIdentity {
  const source = (input ?? {}) as Record<string, unknown>;
  const pick = (field: keyof VisualIdentity, fallback: string) => {
    const value = source[field];
    return typeof value === 'string' && value.length > 0 ? value : fallback;
  };
  const firstOf = (kind: VisualKind, fallback: string) =>
    visualItems(catalog, kind)[0]?.key ?? fallback;
  const itemFor = (key: string, kind: VisualKind, fallback: string) => {
    const item = visualItem(catalog, key);
    return item && item.kind === kind ? item.key : fallback;
  };
  const rawVersion = source.catalog_version;
  const catalogVersion: string | number =
    typeof rawVersion === 'string' || typeof rawVersion === 'number'
      ? rawVersion
      : catalogVersionOf(catalog);
  return {
    icon_key: itemFor(
      pick('icon_key', DEFAULT_IDENTITY.icon_key),
      'icon',
      firstOf('icon', DEFAULT_IDENTITY.icon_key),
    ),
    frame_key: itemFor(
      pick('frame_key', DEFAULT_IDENTITY.frame_key),
      'frame',
      firstOf('frame', DEFAULT_IDENTITY.frame_key),
    ),
    accent_key: itemFor(
      pick('accent_key', DEFAULT_IDENTITY.accent_key),
      'accent',
      firstOf('accent', DEFAULT_IDENTITY.accent_key),
    ),
    entry_key: itemFor(
      pick('entry_key', DEFAULT_IDENTITY.entry_key),
      'entry',
      firstOf('entry', DEFAULT_IDENTITY.entry_key),
    ),
    emote_key: itemFor(
      pick('emote_key', DEFAULT_IDENTITY.emote_key),
      'emote',
      firstOf('emote', DEFAULT_IDENTITY.emote_key),
    ),
    badge_key: itemFor(
      pick('badge_key', DEFAULT_IDENTITY.badge_key),
      'badge',
      firstOf('badge', DEFAULT_IDENTITY.badge_key),
    ),
    catalog_version: String(catalogVersion).length > 0 ? catalogVersion : 'local',
  };
}

/**
 * `true` quando só o fallback local está disponível. Nesse caso o app não pode
 * inventar chaves para o servidor: elas precisam vir de `GET /me/visual`.
 */
export function isLocalVisualCatalog(catalog: VisualCatalog): boolean {
  return (
    catalog === LOCAL_VISUAL_CATALOG ||
    catalogVersionOf(catalog) === catalogVersionOf(LOCAL_VISUAL_CATALOG)
  );
}

/**
 * Corpo seguro para `PUT /me/visual`. A montagem pura fica em
 * `visualPayload.ts`; aqui só decidimos se o catálogo é o fallback local.
 */
export function visualUpdatePayload(
  identity: VisualIdentity,
  catalog: VisualCatalog,
  confirmed?: Partial<VisualIdentityResponse> | Partial<VisualIdentity> | null,
): VisualPayload | null {
  return buildVisualPayload({
    identity,
    catalog,
    confirmed,
    localOnly: isLocalVisualCatalog(catalog),
  });
}

/** Identidade determinística para participantes sem dados visuais no payload. */
export function identityFromSeed(seed: string, catalog = LOCAL_VISUAL_CATALOG): VisualIdentity {
  let hash = 0;
  for (let index = 0; index < seed.length; index += 1) {
    hash = (hash * 31 + seed.charCodeAt(index)) >>> 0;
  }
  const icons = visualItems(catalog, 'icon');
  const accents = visualItems(catalog, 'accent');
  const frames = visualItems(catalog, 'frame');
  const badges = visualItems(catalog, 'badge');
  return normalizeIdentity(
    {
      icon_key: icons[hash % Math.max(1, icons.length)]?.key ?? DEFAULT_IDENTITY.icon_key,
      accent_key: accents[hash % Math.max(1, accents.length)]?.key ?? DEFAULT_IDENTITY.accent_key,
      frame_key: frames[hash % Math.max(1, frames.length)]?.key ?? DEFAULT_IDENTITY.frame_key,
      badge_key: badges[hash % Math.max(1, badges.length)]?.key ?? DEFAULT_IDENTITY.badge_key,
      catalog_version: catalogVersionOf(catalog),
    },
    catalog,
  );
}
