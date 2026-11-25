import { View } from 'react-native';

import type { VisualIdentity } from '../api/types';
import { IdentityBadge } from './IdentityBadge';
import type { Palette } from './theme';

export type TierKey = 'bronze' | 'prata' | 'ouro' | 'platina' | 'diamante';

type EmblemMetal = {
  label: string;
  /** Aro mais escuro, para separar do fundo claro ou escuro. */
  rim: string;
  /** Metal principal do aro externo. */
  metal: string;
  /** Disco interno do emblema. */
  disc: string;
  /** Brilho sólido do aro (sem gradiente). */
  shine: string;
};

const TIER_EMBLEMS: Record<TierKey, EmblemMetal> = {
  bronze: {
    label: 'Bronze',
    rim: '#3D2415',
    metal: '#8A5A34',
    disc: '#B77A4D',
    shine: '#F0C08A',
  },
  prata: {
    label: 'Prata',
    rim: '#343C44',
    metal: '#8E9BA6',
    disc: '#B9C5CE',
    shine: '#FFFFFF',
  },
  ouro: {
    label: 'Ouro',
    rim: '#4A370D',
    metal: '#B8891F',
    disc: '#D9B53F',
    shine: '#FFF2A8',
  },
  platina: {
    label: 'Platina',
    rim: '#303B46',
    metal: '#7D8E9E',
    disc: '#B6C9D6',
    shine: '#FFFFFF',
  },
  diamante: {
    label: 'Diamante',
    rim: '#1C354C',
    metal: '#4F86B8',
    disc: '#86BEDC',
    shine: '#E8FBFF',
  },
};

/** `Provisório`, vazio ou valor desconhecido cai em bronze. */
export function tierKeyOf(tier: string | null | undefined): TierKey {
  const value = (tier ?? '').trim().toLowerCase();
  if (value.startsWith('prat')) {
    return 'prata';
  }
  if (value.startsWith('our') || value.startsWith('gold')) {
    return 'ouro';
  }
  if (value.startsWith('plat') || value.startsWith('platinum')) {
    return 'platina';
  }
  if (value.startsWith('diam') || value.startsWith('diamond')) {
    return 'diamante';
  }
  return 'bronze';
}

export function tierLabel(tier: string | null | undefined): string {
  return TIER_EMBLEMS[tierKeyOf(tier)].label;
}

/**
 * Emblema do elo: aro escuro, metal externo, disco e brilho sólido, com o
 * ícone de identidade no centro. Tudo com Views e cores planas — sem filtros
 * nem gradientes, que não renderizam de forma confiável no Android.
 */
export function TierEmblem({
  tier,
  size,
  identity,
  palette,
}: {
  tier: string | null | undefined;
  size: number;
  identity: Partial<VisualIdentity> | null | undefined;
  palette: Palette;
}) {
  const metal = TIER_EMBLEMS[tierKeyOf(tier)];
  const badgeSize = Math.max(48, size - 24);
  return (
    <View
      accessible
      accessibilityRole="image"
      accessibilityLabel={`Emblema ${metal.label}`}
      style={{
        width: size,
        height: size,
        borderRadius: size / 2,
        backgroundColor: metal.rim,
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <View
        style={{
          width: size - 4,
          height: size - 4,
          borderRadius: (size - 4) / 2,
          backgroundColor: metal.metal,
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <View
          style={{
            width: size - 12,
            height: size - 12,
            borderRadius: (size - 12) / 2,
            backgroundColor: metal.disc,
            borderWidth: 2,
            borderColor: metal.shine,
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <IdentityBadge size={badgeSize} identity={identity} palette={palette} />
        </View>
        {/* Brilho sólido no canto superior esquerdo do metal. */}
        <View
          pointerEvents="none"
          style={{
            position: 'absolute',
            top: size * 0.06,
            left: size * 0.16,
            width: size * 0.38,
            height: Math.max(3, size * 0.08),
            borderRadius: 999,
            backgroundColor: metal.shine,
            opacity: 0.55,
            transform: [{ rotate: '-24deg' }],
          }}
        />
      </View>
    </View>
  );
}
