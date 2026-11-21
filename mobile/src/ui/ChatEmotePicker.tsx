import { useMemo } from 'react';
import { Pressable, ScrollView, View, useWindowDimensions } from 'react-native';

import type { VisualCatalog, VisualItem } from '../api/types';
import { useTheme } from '../state/context';
import { catalogEmote, emoteIcon, isEmoteOnly, parseEmoteBody, type EmoteSegment } from './emote';
import { ICONS } from './icon-data';
import { Icon } from './icons';
import { Btn, TextBtn, Txt } from './kit';
import { Text } from './text';

const TILE_GAP = 8;

function EmoteGlyph({
  segment,
  compact,
}: {
  segment: Extract<EmoteSegment, { type: 'emote' }>;
  compact?: boolean;
}) {
  const { palette } = useTheme();
  const size = compact ? 26 : 18;
  const icon =
    segment.icon && Object.prototype.hasOwnProperty.call(ICONS, segment.icon) ? segment.icon : null;
  return (
    <View
      accessible
      accessibilityRole="image"
      accessibilityLabel={`Emote: ${segment.name}`}
      style={{ flexDirection: 'row', alignItems: 'center', gap: 3 }}
    >
      {icon ? (
        <Icon name={icon} size={size} color={palette.ink} />
      ) : (
        <Text
          maxFontSizeMultiplier={1.3}
          style={{
            fontSize: compact ? 15 : 13,
            fontWeight: '800',
            color: palette.ink,
          }}
        >
          {segment.name}
        </Text>
      )}
    </View>
  );
}

/**
 * Corpo de mensagem de jogador com emotes resolvidos. Mensagem sem token, ou
 * com token desconhecido, continua exatamente como texto puro.
 */
export function ChatEmoteBody({ body, catalog }: { body: string; catalog: VisualCatalog }) {
  const { palette } = useTheme();
  const segments = useMemo(() => parseEmoteBody(body, catalog), [body, catalog]);
  const only = isEmoteOnly(segments);
  if (segments.length === 0) {
    return null;
  }
  return (
    <View
      accessible={false}
      style={{
        marginTop: only ? 4 : 3,
        flexDirection: 'row',
        flexWrap: 'wrap',
        alignItems: 'center',
        gap: 4,
      }}
    >
      {segments.map((segment, index) =>
        segment.type === 'emote' ? (
          <EmoteGlyph key={`emote-${segment.key}-${index}`} segment={segment} compact={only} />
        ) : (
          <Text
            key={`text-${index}`}
            maxFontSizeMultiplier={1.3}
            style={{ fontSize: 14, color: palette.ink }}
          >
            {segment.text}
          </Text>
        ),
      )}
    </View>
  );
}

export type ChatEmotePickerProps = {
  items: VisualItem[];
  catalog: VisualCatalog;
  onPick: (item: VisualItem) => void;
  /** Chaves com envio em andamento; só esses tiles ficam bloqueados. */
  busyKeys?: string[];
  /** `true` com catálogo local/ausente: nenhum emote pode ser enviado. */
  unavailable?: boolean;
  retrying?: boolean;
  onRetry: () => void;
  onOpenTrack: () => void;
  onClose: () => void;
};

/**
 * Painel inline de emotes, montado acima do composer pelos chats. Não busca
 * rede: recebe a lista já filtrada do catálogo do servidor.
 */
export function ChatEmotePicker({
  items,
  catalog,
  onPick,
  busyKeys = [],
  unavailable = false,
  retrying = false,
  onRetry,
  onOpenTrack,
  onClose,
}: ChatEmotePickerProps) {
  const { palette } = useTheme();
  const { width } = useWindowDimensions();
  const columns = width >= 360 ? 4 : 3;
  const tileWidth = Math.max(
    44,
    Math.floor((width - 32 - 20 - TILE_GAP * (columns - 1)) / columns),
  );
  const busy = new Set(busyKeys);

  return (
    <View
      accessibilityLabel="Emotes"
      style={{
        borderWidth: 1.5,
        borderColor: palette.line,
        borderRadius: 14,
        backgroundColor: palette.surface,
        padding: 10,
        gap: 8,
      }}
    >
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
        <Txt variant="label">Emotes</Txt>
        <TextBtn muted onPress={onClose}>
          Fechar
        </TextBtn>
      </View>
      {unavailable ? (
        <View style={{ gap: 6 }}>
          <Txt variant="tiny">Emotes indisponíveis agora.</Txt>
          <Btn small tone="ghost" onPress={onRetry} disabled={retrying}>
            {retrying ? 'Buscando…' : 'Tentar de novo'}
          </Btn>
        </View>
      ) : items.length === 0 ? (
        <View style={{ gap: 6 }}>
          <Txt variant="tiny">Nenhum emote liberado ainda.</Txt>
          <Txt variant="tiny">Emotes novos entram pelo passe da temporada.</Txt>
          <Btn small tone="ghost" onPress={onOpenTrack}>
            Ver trilha
          </Btn>
        </View>
      ) : (
        <ScrollView
          style={{ maxHeight: 186 }}
          contentContainerStyle={{ gap: TILE_GAP }}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: TILE_GAP }}>
            {items.map((item) => {
              const selected = busy.has(item.key);
              const catalogItem = catalogEmote(catalog, item.key);
              const iconName = catalogItem ? emoteIcon(catalogItem) : null;
              const glyph =
                iconName && Object.prototype.hasOwnProperty.call(ICONS, iconName) ? iconName : null;
              return (
                <Pressable
                  key={item.key}
                  onPress={() => onPick(item)}
                  disabled={selected}
                  accessibilityRole="button"
                  accessibilityLabel={`Enviar emote ${item.name}`}
                  accessibilityState={{ disabled: selected, busy: selected }}
                  style={({ pressed }) => ({
                    width: tileWidth,
                    minHeight: 56,
                    borderRadius: 10,
                    paddingHorizontal: 4,
                    paddingVertical: 5,
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 3,
                    opacity: selected ? 0.5 : pressed ? 0.85 : 1,
                  })}
                >
                  {glyph ? <Icon name={glyph} size={28} color={palette.ink} /> : null}
                  <Text
                    numberOfLines={1}
                    ellipsizeMode="tail"
                    maxFontSizeMultiplier={1.3}
                    style={{
                      maxWidth: '100%',
                      fontSize: 11,
                      fontWeight: '700',
                      color: palette.ink,
                    }}
                  >
                    {item.name}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </ScrollView>
      )}
    </View>
  );
}
