import { View } from 'react-native';

import type { VisualCatalog, VisualIdentity } from '../api/types';

import { Icon } from './icons';
import {
  DEFAULT_IDENTITY,
  iconNameFor,
  itemColor,
  LOCAL_VISUAL_CATALOG,
  visualItem,
} from './identity';
import type { Palette } from './theme';

export type IdentityBadgeProps = {
  size?: number;
  identity?: Partial<VisualIdentity> | null;
  catalog?: VisualCatalog;
  palette: Palette;
  /** Sobrescreve o selo do contrato (ex.: conquista temporária na tela). */
  badgeKey?: string | null;
  showBadge?: boolean;
};

function readableInk(background: string, palette: Palette): string {
  const hex = background.replace('#', '');
  if (hex.length < 6) {
    return palette.ink;
  }
  const red = parseInt(hex.slice(0, 2), 16);
  const green = parseInt(hex.slice(2, 4), 16);
  const blue = parseInt(hex.slice(4, 6), 16);
  const luminance = (0.299 * red + 0.587 * green + 0.114 * blue) / 255;
  return luminance > 0.62 ? '#17191B' : '#F1F3F0';
}

export function IdentityBadge({
  size = 48,
  identity,
  catalog = LOCAL_VISUAL_CATALOG,
  palette,
  badgeKey,
  showBadge = true,
}: IdentityBadgeProps) {
  const current = { ...DEFAULT_IDENTITY, ...(identity ?? {}) };
  const icon = iconNameFor(catalog, current.icon_key, 'user');
  const frame = visualItem(catalog, current.frame_key);
  const frameColor = frame?.asset_ref
    ? itemColor(catalog, current.frame_key, palette.lineStrong)
    : palette.surface2;
  const accent = itemColor(catalog, current.accent_key, palette.surface2);
  const ink = readableInk(accent, palette);
  const padding = Math.max(2, Math.round(size * 0.045));
  const key = badgeKey === undefined ? current.badge_key : badgeKey;
  const badgeItem = visualItem(catalog, key ?? undefined);
  const badgeIcon = badgeItem?.asset_ref ? iconNameFor(catalog, badgeItem.key, 'shield') : null;
  const badgeSize = Math.max(14, Math.round(size * 0.3));
  return (
    <View
      accessibilityRole="image"
      accessibilityLabel={`Identidade ${badgeItem?.name ?? 'do jogador'}`}
      style={{
        width: size,
        height: size,
        borderRadius: size / 2,
        padding,
        backgroundColor: frameColor,
        flexShrink: 0,
      }}
    >
      <View
        style={{
          flex: 1,
          borderRadius: size / 2,
          backgroundColor: accent,
          alignItems: 'center',
          justifyContent: 'center',
          overflow: 'hidden',
        }}
      >
        <Icon name={icon} size={Math.round(size * 0.5)} color={ink} strokeWidth={2} />
      </View>
      {showBadge && badgeIcon ? (
        <View
          style={{
            position: 'absolute',
            right: -2,
            bottom: -2,
            width: badgeSize,
            height: badgeSize,
            borderRadius: badgeSize / 2,
            borderWidth: 1.5,
            borderColor: palette.surface,
            backgroundColor: palette.ink,
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Icon
            name={badgeIcon}
            size={Math.round(badgeSize * 0.6)}
            color={palette.onInk}
            strokeWidth={2}
          />
        </View>
      ) : null}
    </View>
  );
}
