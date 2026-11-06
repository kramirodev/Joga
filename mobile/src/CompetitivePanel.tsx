import { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

import {
  ApiError,
  profileApi,
  ratingsApi,
  type MyRating,
  type RankingPage,
  type SportFormat,
} from './api';
import { loadSession } from './session';

type FormatOption = SportFormat & { sportName: string };

const DIVISION_LABELS: Record<string, string> = {
  PROVISIONAL: 'Provisório',
  BRONZE: 'Bronze',
  SILVER: 'Prata',
  GOLD: 'Ouro',
  PLATINUM: 'Platina',
  DIAMOND: 'Diamante',
};

const DIVISION_COLORS: Record<string, string> = {
  PROVISIONAL: '#52625a',
  BRONZE: '#9a5b2d',
  SILVER: '#6f7d86',
  GOLD: '#b8860b',
  PLATINUM: '#2f7f86',
  DIAMOND: '#4b5bd6',
};

function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    return `${error.code} (HTTP ${error.status})`;
  }
  if (error instanceof Error && error.message.length > 0) {
    return error.message;
  }
  return 'Falha inesperada.';
}

function divisionLabel(value: string): string {
  return DIVISION_LABELS[value] ?? value;
}

function formatLabel(format: FormatOption): string {
  return `${format.sportName} • ${format.name}`;
}

export function CompetitivePanel() {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [formats, setFormats] = useState<FormatOption[]>([]);
  const [selectedFormat, setSelectedFormat] = useState('');
  const [rating, setRating] = useState<MyRating | null>(null);
  const [ranking, setRanking] = useState<RankingPage | null>(null);
  const [message, setMessage] = useState('Entre na conta para ver sua divisão e o ranking.');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    void (async () => {
      const session = await loadSession();
      if (!session) {
        return;
      }
      try {
        const catalog = await profileApi.catalog();
        const options = catalog.sports.flatMap((sport) =>
          sport.formats.map((format) => ({ ...format, sportName: sport.name })),
        );
        let preferred = options[0]?.id ?? '';
        try {
          const profile = await profileApi.getProfile(session.accessToken);
          preferred = profile.sports[0]?.format_id ?? preferred;
        } catch {
          // Perfil ainda não configurado: usa o primeiro formato do catálogo.
        }
        if (!active) {
          return;
        }
        setAccessToken(session.accessToken);
        setFormats(options);
        setSelectedFormat(preferred);
        if (preferred) {
          const [myRating, page] = await Promise.all([
            ratingsApi.myRating(session.accessToken, preferred),
            ratingsApi.ranking(session.accessToken, preferred),
          ]);
          if (!active) {
            return;
          }
          setRating(myRating);
          setRanking(page);
          setMessage('Competitivo carregado.');
        } else {
          setMessage('Nenhum formato disponível para ranking.');
        }
      } catch (error) {
        if (active) {
          setMessage(describeError(error));
        }
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  async function loadFormat(formatId: string) {
    if (!accessToken) {
      return;
    }
    setBusy(true);
    try {
      const [myRating, page] = await Promise.all([
        ratingsApi.myRating(accessToken, formatId),
        ratingsApi.ranking(accessToken, formatId),
      ]);
      setRating(myRating);
      setRanking(page);
      setSelectedFormat(formatId);
      setMessage('Competitivo atualizado.');
    } catch (error) {
      setMessage(describeError(error));
    } finally {
      setBusy(false);
    }
  }

  async function refresh() {
    if (selectedFormat) {
      await loadFormat(selectedFormat);
    }
  }

  const division = rating?.division ?? 'PROVISIONAL';
  const progress = rating?.progress;
  const provisional = rating?.provisional ?? true;

  return (
    <View style={styles.section}>
      <Text style={styles.eyebrow}>FASE 8 • COMPETITIVO</Text>
      <Text style={styles.heading}>Sua divisão e o ranking</Text>
      <Text style={styles.body}>
        O app mostra divisão, progresso e posição. O MMR bruto e o Trust Factor permanecem internos.
      </Text>

      <View style={styles.chips}>
        {formats.map((format) => {
          const selected = format.id === selectedFormat;
          return (
            <Pressable
              accessibilityRole="button"
              accessibilityState={{ selected }}
              key={format.id}
              onPress={() => void loadFormat(format.id)}
              style={[styles.chip, selected && styles.chipSelected]}
            >
              <Text style={[styles.chipText, selected && styles.chipTextSelected]}>
                {formatLabel(format)}
              </Text>
            </Pressable>
          );
        })}
      </View>

      <View style={styles.card}>
        <Text style={styles.label}>Sua divisão</Text>
        <Text style={[styles.division, { color: DIVISION_COLORS[division] ?? '#173b2a' }]}>
          {divisionLabel(division)}
        </Text>
        {provisional ? (
          <Text style={styles.value}>
            Colocação em andamento • faltam {rating?.placement_matches_remaining ?? 5} partida(s)
          </Text>
        ) : (
          <>
            <View
              accessibilityLabel={`Progresso na divisão: ${Math.round((progress ?? 0) * 100)}%`}
              style={styles.progressTrack}
            >
              <View
                style={[styles.progressFill, { width: `${Math.round((progress ?? 0) * 100)}%` }]}
              />
            </View>
            <Text style={styles.value}>
              {rating?.next_division
                ? `Próxima divisão: ${divisionLabel(rating.next_division)}`
                : 'Divisão máxima'}
            </Text>
          </>
        )}
        <View style={styles.stats}>
          <View style={styles.stat}>
            <Text style={styles.label}>Posição</Text>
            <Text style={styles.statValue}>{rating?.position ?? '—'}</Text>
          </View>
          <View style={styles.stat}>
            <Text style={styles.label}>Partidas</Text>
            <Text style={styles.statValue}>{rating?.matches_played ?? 0}</Text>
          </View>
        </View>
      </View>

      <View style={styles.card}>
        <Text style={styles.label}>Top do formato</Text>
        {ranking && ranking.entries.length > 0 ? (
          ranking.entries.map((entry) => (
            <View key={entry.user_id} style={styles.rankingRow}>
              <Text style={styles.position}>{entry.position}º</Text>
              <View style={styles.rankingIdentity}>
                <Text style={styles.rankingName}>{entry.display_name ?? 'Jogador'}</Text>
                <Text style={styles.rankingMeta}>
                  {divisionLabel(entry.division)} • {entry.matches_played} partidas
                </Text>
              </View>
            </View>
          ))
        ) : (
          <Text style={styles.value}>
            Nenhum jogador colocado neste formato ainda. Complete 5 partidas ranqueadas.
          </Text>
        )}
      </View>

      <Pressable
        accessibilityRole="button"
        disabled={busy || !selectedFormat}
        onPress={() => void refresh()}
        style={({ pressed }) => [
          styles.button,
          pressed && styles.buttonPressed,
          (busy || !selectedFormat) && styles.buttonDisabled,
        ]}
      >
        {busy ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.buttonText}>Atualizar competitivo</Text>
        )}
      </Pressable>

      <Text accessibilityLiveRegion="polite" style={styles.message}>
        {message}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  section: { gap: 12 },
  eyebrow: { color: '#26724a', fontSize: 12, fontWeight: '700', letterSpacing: 1.2 },
  heading: { color: '#173b2a', fontSize: 21, fontWeight: '700' },
  body: { color: '#52625a', fontSize: 15, lineHeight: 22 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: {
    borderColor: '#b8cdc0',
    borderRadius: 999,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  chipSelected: { backgroundColor: '#26724a', borderColor: '#26724a' },
  chipText: { color: '#26724a', fontSize: 13, fontWeight: '600' },
  chipTextSelected: { color: '#fff' },
  card: { backgroundColor: '#fff', borderRadius: 14, padding: 16, gap: 8 },
  label: { color: '#52625a', fontSize: 12, fontWeight: '700', textTransform: 'uppercase' },
  value: { color: '#173b2a', fontSize: 15, lineHeight: 22 },
  division: { fontSize: 32, fontWeight: '800' },
  progressTrack: {
    backgroundColor: '#e4ece7',
    borderRadius: 999,
    height: 10,
    overflow: 'hidden',
  },
  progressFill: { backgroundColor: '#26724a', height: 10 },
  stats: { flexDirection: 'row', gap: 24 },
  stat: { gap: 2 },
  statValue: { color: '#173b2a', fontSize: 20, fontWeight: '700' },
  rankingRow: {
    alignItems: 'center',
    borderTopColor: '#e4ece7',
    borderTopWidth: 1,
    flexDirection: 'row',
    gap: 12,
    paddingTop: 10,
  },
  position: { color: '#26724a', fontSize: 16, fontWeight: '800', width: 42 },
  rankingIdentity: { flex: 1, gap: 2 },
  rankingName: { color: '#173b2a', fontSize: 15, fontWeight: '600' },
  rankingMeta: { color: '#52625a', fontSize: 13 },
  button: {
    alignItems: 'center',
    backgroundColor: '#26724a',
    borderRadius: 12,
    justifyContent: 'center',
    minHeight: 50,
    padding: 14,
  },
  buttonPressed: { opacity: 0.82 },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { color: '#fff', fontSize: 15, fontWeight: '700' },
  message: { color: '#52625a', fontSize: 13, lineHeight: 20 },
});
