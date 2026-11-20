import { useState } from 'react';
import { Pressable, ScrollView, View } from 'react-native';

import { useApp } from '../state/app';
import { useNav, useTheme } from '../state/context';
import {
  entryMode,
  formatLabelFromCatalog,
  modeLabel,
  oldestCreatedAt,
  queueFailureMessage,
  summarizeEntries,
} from '../state/queueState';
import { useActiveInterval } from '../state/useActiveInterval';
import { elapsed } from './datetime';
import { Btn, BtnRow, Notice, Txt } from './kit';
import { Text } from './text';

/**
 * Indicador persistente da fila multi-entrada. Fica no fluxo, logo acima da tab
 * bar (ou acima do inset inferior quando não há tab bar), então nunca cobre o
 * conteúdo nem empurra a navegação para fora da tela.
 */
export function QueueIndicator() {
  const nav = useNav();
  const { palette, contentBottomInset } = useTheme();
  const {
    queue,
    matchedEntry,
    catalog,
    cancelQueue,
    queueReconnecting,
    queueNotice,
    clearQueueNotice,
  } = useApp();
  const [expanded, setExpanded] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(() => new Date());

  useActiveInterval(() => setNow(new Date()), 1000, queue.length > 0);

  if (queue.length === 0 && !matchedEntry && !queueNotice) {
    return null;
  }

  const summary = summarizeEntries(queue);
  const names = Array.from(
    new Set(summary.formats.map((item) => formatLabelFromCatalog(catalog, item.formatId))),
  );
  const modes = summary.modes.map((item) => modeLabel(item.mode));
  const countLabel =
    queue.length === 0
      ? 'Nenhuma entrada aguardando'
      : `${queue.length} ${queue.length === 1 ? 'busca ativa' : 'buscas ativas'}`;
  const title = matchedEntry ? 'Partida encontrada' : countLabel;
  const subtitle = matchedEntry
    ? `${formatLabelFromCatalog(catalog, matchedEntry.format_id)} · ${modeLabel(entryMode(matchedEntry))}`
    : (queueNotice ??
      [
        names.length > 0
          ? names.slice(0, 2).join(', ') + (names.length > 2 ? ` +${names.length - 2}` : '')
          : null,
        modes.length > 0 ? modes.join(' + ') : null,
      ]
        .filter(Boolean)
        .join(' · '));
  const since = oldestCreatedAt(queue) ?? matchedEntry?.created_at ?? null;
  const cancelTarget = queue.length;

  const cancel = async () => {
    if (busy) {
      return;
    }
    setBusy(true);
    setError(null);
    const result = await cancelQueue();
    if (result.ok) {
      setBusy(false);
      setConfirming(false);
      setExpanded(false);
      nav.reset('home');
      nav.toast('Buscas canceladas.');
      return;
    }
    setError(queueFailureMessage(result.code));
    setBusy(false);
  };

  return (
    <View style={{ flexShrink: 0, backgroundColor: palette.bg, paddingBottom: contentBottomInset }}>
      <View
        style={{
          marginHorizontal: 10,
          marginBottom: 6,
          borderWidth: 1.5,
          borderColor: palette.lineStrong,
          borderRadius: 14,
          backgroundColor: palette.surface,
          paddingHorizontal: 12,
          paddingVertical: 8,
          gap: 8,
        }}
      >
        <Pressable
          onPress={() => setExpanded((current) => !current)}
          accessibilityRole="button"
          accessibilityState={{ expanded }}
          accessibilityLabel={`${title}. ${subtitle}. Toque para ${expanded ? 'recolher' : 'ver detalhes'}.`}
          style={({ pressed }) => ({
            minHeight: 48,
            flexDirection: 'row',
            alignItems: 'center',
            gap: 10,
            opacity: pressed ? 0.9 : 1,
          })}
        >
          <View style={{ flex: 1, minWidth: 0 }}>
            <Text
              numberOfLines={1}
              accessibilityLiveRegion="polite"
              style={{ fontSize: 14, fontWeight: '900', color: palette.ink }}
            >
              {title}
            </Text>
            {subtitle ? (
              <Text numberOfLines={1} style={{ fontSize: 12, color: palette.muted }}>
                {subtitle}
              </Text>
            ) : (
              <Text numberOfLines={1} style={{ fontSize: 12, color: palette.muted }}>
                A partida encontrada é a única pendência.
              </Text>
            )}
          </View>
          {queueReconnecting ? (
            <Text style={{ fontSize: 11, fontWeight: '800', color: palette.orange }}>
              reconectando
            </Text>
          ) : null}
          {since ? (
            <Text style={{ fontSize: 13, fontWeight: '800', color: palette.ink }}>
              {elapsed(since, now)}
            </Text>
          ) : null}
          <Text style={{ fontSize: 14, color: palette.muted }}>{expanded ? '▾' : '▸'}</Text>
        </Pressable>
        {expanded ? (
          <View style={{ gap: 8 }}>
            {matchedEntry ? (
              <View style={{ gap: 4 }}>
                <Txt variant="tiny">
                  O servidor fechou esta entrada; as demais seguem aguardando.
                </Txt>
                {matchedEntry.lobby ? (
                  <Btn
                    tone="primary"
                    small
                    onPress={() =>
                      matchedEntry.lobby &&
                      nav.go('lobby-found', {
                        lobbyId: matchedEntry.lobby.id,
                        mode: matchedEntry.mode,
                      })
                    }
                  >
                    Ver partida
                  </Btn>
                ) : null}
              </View>
            ) : null}
            {queue.length > 0 ? (
              <ScrollView
                style={{ maxHeight: 168 }}
                keyboardShouldPersistTaps="handled"
                showsVerticalScrollIndicator={false}
              >
                <View style={{ gap: 10 }}>
                  {queue.map((entry) => (
                    <View
                      key={entry.id}
                      style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}
                    >
                      <View style={{ flex: 1, minWidth: 0 }}>
                        <Text
                          numberOfLines={1}
                          style={{ fontSize: 13, fontWeight: '800', color: palette.ink }}
                        >
                          {formatLabelFromCatalog(catalog, entry.format_id)}
                        </Text>
                        <Text style={{ fontSize: 11, color: palette.muted }}>
                          {modeLabel(entryMode(entry))}
                        </Text>
                      </View>
                      <Text style={{ fontSize: 12, fontWeight: '700', color: palette.ink }}>
                        {elapsed(entry.created_at, now)}
                      </Text>
                    </View>
                  ))}
                </View>
              </ScrollView>
            ) : null}
            {error ? (
              <Notice tone="orange" icon="alert">
                {error}
              </Notice>
            ) : null}
            {queueNotice ? (
              <View style={{ gap: 6 }}>
                <Notice tone="orange" icon="alert">
                  {queueNotice}
                </Notice>
                <Btn small tone="ghost" onPress={clearQueueNotice}>
                  Dispensar aviso
                </Btn>
              </View>
            ) : null}
            {confirming ? (
              <View style={{ gap: 6 }}>
                <Txt variant="tiny">
                  Cancelar as {cancelTarget} {cancelTarget === 1 ? 'busca' : 'buscas'} aguardando? A
                  partida encontrada, se houver, não é cancelada aqui. Se a rede falhar, as entradas
                  continuam aqui.
                </Txt>
                <BtnRow>
                  <Btn small tone="ghost" onPress={() => setConfirming(false)} disabled={busy}>
                    Manter
                  </Btn>
                  <Btn small tone="danger" onPress={cancel} disabled={busy}>
                    {busy ? 'Cancelando…' : 'Cancelar tudo'}
                  </Btn>
                </BtnRow>
              </View>
            ) : (
              <BtnRow>
                <Btn small tone="ghost" onPress={() => nav.go('queue-search')}>
                  Ver
                </Btn>
                <Btn small tone="ghost" onPress={() => nav.go('queue', { from: 'queue-search' })}>
                  Alterar
                </Btn>
                <Btn
                  small
                  tone="danger"
                  onPress={() => setConfirming(true)}
                  disabled={busy || queue.length === 0}
                >
                  Cancelar
                </Btn>
              </BtnRow>
            )}
          </View>
        ) : null}
      </View>
    </View>
  );
}
