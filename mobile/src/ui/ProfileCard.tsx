import { Pressable, View, useWindowDimensions } from 'react-native';

import type { VisualIdentity } from '../api/types';
import { useTheme } from '../state/context';
import { Card } from './kit';
import { Icon } from './icons';
import { Text } from './text';
import { ThemeArt } from './themeArtView';
import { themeById } from './themes';
import { TierEmblem } from './TierEmblem';

export type ProfileCardData = {
  name: string;
  tag: string;
  clanName: string;
  tier: string;
  level: number;
  qualifier: string;
  seasonLabel: string;
  record: number;
  visual: Partial<VisualIdentity> | null | undefined;
};

/**
 * Cartão do perfil montado uma única vez e reutilizado na tela, na prévia e na
 * captura. `imageMode` só troca a moldura para 3:4 (1080×1440), sem mudar a arte,
 * o emblema, as pílulas ou os quadros de insígnia.
 */
export function ProfileCard({
  data,
  imageMode = false,
  width,
  height,
  onPressAvatar,
}: {
  data: ProfileCardData;
  imageMode?: boolean;
  width?: number;
  height?: number;
  /** Toque no emblema/avatar; a imagem compartilhável não recebe ação. */
  onPressAvatar?: () => void;
}) {
  const { palette, themeId } = useTheme();
  const theme = themeById(themeId);
  const window = useWindowDimensions();
  const compact = window.width < 360;
  const cardWidth = width ?? window.width - 32;
  const cardHeight = height ?? (imageMode ? Math.round(cardWidth * (4 / 3)) : compact ? 420 : 440);
  const emblemSize = compact ? 84 : 92;
  const nameSize = compact ? 28 : 30;
  const artText = theme.dark ? '#FFFFFF' : palette.ink;
  const artShadow = {
    textShadowColor: theme.dark ? 'rgba(0, 0, 0, 0.82)' : 'rgba(255, 255, 255, 0.92)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 6,
  };
  const pillBackground = theme.dark ? 'rgba(255, 255, 255, 0.26)' : 'rgba(255, 255, 255, 0.6)';
  const pillBorder = theme.dark ? 'rgba(255, 255, 255, 0.36)' : 'rgba(0, 0, 0, 0.18)';
  const pillIconColor = theme.dark ? '#FFFFFF' : palette.brand;
  const honorFrames = [
    { key: 'season', icon: 'trophy' as const, label: data.seasonLabel },
    { key: 'founder', icon: 'crown' as const, label: 'FUNDADOR' },
    { key: 'badge', icon: 'shield' as const, label: 'A CONQUISTAR' },
  ];
  // A tag chega sem `#`; ausência nunca vira uma tag fake.
  const tagText = data.tag && data.tag !== '—' ? `#${data.tag}` : '—';

  return (
    <Card
      padding={0}
      style={{
        width: imageMode ? cardWidth : undefined,
        ...(imageMode ? { height: cardHeight } : null),
        overflow: 'hidden',
      }}
    >
      <View
        pointerEvents="none"
        accessibilityElementsHidden
        importantForAccessibility="no-hide-descendants"
        style={{ position: 'absolute', top: 0, right: 0, bottom: 0, left: 0 }}
      >
        <ThemeArt art={theme.art} />
      </View>
      {/* Scrim único em faixas: a arte fica inteira visível no topo e ganha
          contraste crescente só na metade inferior, onde ficam as pílulas. */}
      <View
        pointerEvents="none"
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          bottom: 0,
          height: '58%',
          backgroundColor: palette.bg,
          opacity: theme.dark ? 0.1 : 0.08,
        }}
      />
      <View
        pointerEvents="none"
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          bottom: 0,
          height: '40%',
          backgroundColor: palette.bg,
          opacity: theme.dark ? 0.2 : 0.18,
        }}
      />
      <View
        pointerEvents="none"
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          bottom: 0,
          height: '26%',
          backgroundColor: palette.bg,
          opacity: theme.dark ? 0.34 : 0.3,
        }}
      />
      <View
        pointerEvents="none"
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          bottom: 0,
          height: '12%',
          backgroundColor: palette.bg,
          opacity: theme.dark ? 0.52 : 0.46,
        }}
      />

      <View
        style={{
          minHeight: imageMode ? undefined : cardHeight,
          height: imageMode ? '100%' : undefined,
          padding: 14,
          justifyContent: 'space-between',
        }}
      >
        <View
          style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}
        >
          <Text
            style={[
              artShadow,
              {
                fontSize: 17,
                lineHeight: 19,
                fontWeight: '900',
                letterSpacing: 0.6,
                color: artText,
              },
            ]}
          >
            JOGA<Text style={{ color: palette.brand }}>.</Text>
          </Text>
          <Text
            style={[
              artShadow,
              {
                fontSize: 11,
                lineHeight: 14,
                fontWeight: '800',
                letterSpacing: 0.8,
                color: artText,
                textTransform: 'uppercase',
              },
            ]}
          >
            {data.seasonLabel}
          </Text>
        </View>

        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', paddingTop: 6 }}>
          <View style={{ zIndex: 2 }}>
            {onPressAvatar && !imageMode ? (
              <Pressable
                onPress={onPressAvatar}
                accessibilityRole="button"
                accessibilityLabel="Abrir perfil público"
                hitSlop={8}
                style={({ pressed }) => ({ opacity: pressed ? 0.82 : 1 })}
              >
                <TierEmblem
                  tier={data.tier}
                  size={emblemSize}
                  identity={data.visual}
                  palette={palette}
                />
              </Pressable>
            ) : (
              <TierEmblem
                tier={data.tier}
                size={emblemSize}
                identity={data.visual}
                palette={palette}
              />
            )}
          </View>
          <View style={{ alignItems: 'center', marginTop: -12, zIndex: 1 }}>
            <Text
              style={[
                artShadow,
                {
                  paddingTop: 12,
                  fontSize: nameSize,
                  lineHeight: Math.round(nameSize * 1.05),
                  fontWeight: '900',
                  letterSpacing: -0.6,
                  textAlign: 'center',
                  textTransform: 'uppercase',
                  color: artText,
                },
              ]}
            >
              {data.name}
            </Text>
            <Text
              style={[
                artShadow,
                {
                  marginTop: 4,
                  fontSize: 11,
                  lineHeight: 15,
                  fontWeight: '800',
                  letterSpacing: 1.1,
                  textAlign: 'center',
                  textTransform: 'uppercase',
                  color: artText,
                },
              ]}
            >
              {tagText} · {data.clanName}
            </Text>
          </View>
        </View>

        <View style={{ gap: 8 }}>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <View
              style={{
                flex: 1,
                minWidth: 0,
                flexDirection: 'row',
                alignItems: 'center',
                gap: 8,
                padding: 10,
                borderRadius: 14,
                borderWidth: 1,
                borderColor: pillBorder,
                backgroundColor: pillBackground,
              }}
            >
              <Icon name="shield" size={20} color={pillIconColor} />
              <View style={{ flex: 1, minWidth: 0 }}>
                <Text
                  style={[
                    artShadow,
                    {
                      fontSize: 12,
                      lineHeight: 15,
                      fontWeight: '900',
                      color: artText,
                      textTransform: 'uppercase',
                    },
                  ]}
                >
                  {`${data.tier.toUpperCase()} ${data.level}`}
                </Text>
                <Text
                  style={[
                    artShadow,
                    {
                      marginTop: 1,
                      fontSize: 10.5,
                      lineHeight: 14,
                      fontWeight: '700',
                      color: artText,
                      textTransform: 'uppercase',
                    },
                  ]}
                >
                  {`${data.qualifier} · ${data.seasonLabel}`}
                </Text>
              </View>
            </View>
            <View
              style={{
                flex: 1,
                minWidth: 0,
                flexDirection: 'row',
                alignItems: 'center',
                gap: 8,
                padding: 10,
                borderRadius: 14,
                borderWidth: 1,
                borderColor: pillBorder,
                backgroundColor: pillBackground,
              }}
            >
              <Icon name="flame" size={20} color={pillIconColor} />
              <View style={{ flex: 1, minWidth: 0 }}>
                <Text
                  style={[
                    artShadow,
                    {
                      fontSize: 16,
                      lineHeight: 18,
                      fontWeight: '900',
                      color: artText,
                    },
                  ]}
                >
                  {data.record}
                </Text>
                <Text
                  style={[
                    artShadow,
                    {
                      marginTop: 1,
                      fontSize: 10,
                      lineHeight: 13,
                      fontWeight: '800',
                      letterSpacing: 0.5,
                      color: artText,
                      textTransform: 'uppercase',
                    },
                  ]}
                >
                  VITÓRIAS E DERROTAS
                </Text>
              </View>
            </View>
          </View>

          <View style={{ flexDirection: 'row', gap: 6 }}>
            {honorFrames.map((item) => (
              <View
                key={item.key}
                style={{
                  flex: 1,
                  minWidth: 0,
                  aspectRatio: 1,
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 4,
                  paddingHorizontal: 4,
                  paddingVertical: 6,
                  borderRadius: 12,
                  borderWidth: 1,
                  borderColor: pillBorder,
                  backgroundColor: pillBackground,
                }}
              >
                <Icon name={item.icon} size={22} color={pillIconColor} />
                <Text
                  numberOfLines={2}
                  adjustsFontSizeToFit
                  minimumFontScale={0.7}
                  maxFontSizeMultiplier={1.4}
                  style={[
                    artShadow,
                    {
                      fontSize: 9.5,
                      lineHeight: 12,
                      fontWeight: '900',
                      letterSpacing: 0.2,
                      textAlign: 'center',
                      textTransform: 'uppercase',
                      color: artText,
                    },
                  ]}
                >
                  {item.label}
                </Text>
              </View>
            ))}
          </View>

          <View
            style={{
              flexDirection: 'row',
              alignItems: 'center',
              justifyContent: 'space-between',
              paddingTop: 2,
            }}
          >
            <Text
              style={[
                artShadow,
                {
                  fontSize: 11,
                  lineHeight: 14,
                  fontWeight: '800',
                  color: artText,
                },
              ]}
            >
              {theme.name}
            </Text>
            <View
              accessible
              accessibilityLabel={`Cores do tema ${theme.name}`}
              style={{ flexDirection: 'row', gap: 6 }}
            >
              {[palette.bg, palette.brand, palette.ink].map((color) => (
                <View
                  key={color}
                  style={{
                    width: 14,
                    height: 14,
                    borderRadius: 7,
                    backgroundColor: color,
                    borderWidth: 1,
                    borderColor: theme.dark ? 'rgba(255, 255, 255, 0.8)' : 'rgba(0, 0, 0, 0.4)',
                  }}
                />
              ))}
            </View>
          </View>
        </View>
      </View>
    </Card>
  );
}
