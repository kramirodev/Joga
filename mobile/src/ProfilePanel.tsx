import { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import * as Location from 'expo-location';

import {
  ApiError,
  profileApi,
  type Catalog,
  type Profile,
  type SportFormat,
  type Venue,
} from './api';
import { loadSession } from './session';

type FormatOption = SportFormat & { sportName: string };
type Level = 'beginner' | 'intermediate' | 'advanced';
type CourtPreference = 'PUBLIC_ONLY' | 'PRIVATE_ONLY' | 'ANY';

const WEEKDAYS = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];
const LEVELS: { value: Level; label: string }[] = [
  { value: 'beginner', label: 'Iniciante' },
  { value: 'intermediate', label: 'Intermediário' },
  { value: 'advanced', label: 'Avançado' },
];
const COURTS: { value: CourtPreference; label: string }[] = [
  { value: 'ANY', label: 'Qualquer' },
  { value: 'PUBLIC_ONLY', label: 'Pública' },
  { value: 'PRIVATE_ONLY', label: 'Particular' },
];

function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    return `${error.code} (HTTP ${error.status})`;
  }
  if (error instanceof Error && error.message.length > 0) {
    return error.message;
  }
  return 'Falha inesperada.';
}

function withSeconds(value: string): string {
  return value.length === 5 ? `${value}:00` : value;
}

type WindowDraft = { weekday: number; start: string; end: string };

const TIME_PATTERN = /^([01]\d|2[0-3]):([0-5]\d)$/;

function toMinutes(value: string): number | null {
  const match = TIME_PATTERN.exec(value);
  if (!match) {
    return null;
  }
  return Number(match[1]) * 60 + Number(match[2]);
}

function sortWindows(windows: WindowDraft[]): WindowDraft[] {
  return [...windows].sort((a, b) => a.weekday - b.weekday || a.start.localeCompare(b.start));
}

function weekdayLabel(value: number): string {
  return WEEKDAYS[value - 1] ?? '?';
}

export function ProfilePanel() {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [formats, setFormats] = useState<FormatOption[]>([]);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [displayName, setDisplayName] = useState('');
  const [bio, setBio] = useState('');
  const [selectedFormat, setSelectedFormat] = useState('');
  const [level, setLevel] = useState<Level>('beginner');
  const [court, setCourt] = useState<CourtPreference>('ANY');
  const [weekday, setWeekday] = useState(1);
  const [startTime, setStartTime] = useState('18:00');
  const [endTime, setEndTime] = useState('20:00');
  const [windows, setWindows] = useState<WindowDraft[]>([]);
  const [cep, setCep] = useState('01001000');
  const [radius, setRadius] = useState('10');
  const [venues, setVenues] = useState<Venue[]>([]);
  const [message, setMessage] = useState('Entre na conta para editar o perfil.');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    void (async () => {
      const session = await loadSession();
      if (!session) {
        return;
      }
      try {
        const [catalog, loaded] = await Promise.all([
          profileApi.catalog(),
          profileApi.getProfile(session.accessToken),
        ]);
        if (!active) {
          return;
        }
        setAccessToken(session.accessToken);
        applyCatalog(catalog);
        applyProfile(loaded);
        setMessage('Perfil carregado.');
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

  function applyCatalog(catalog: Catalog) {
    setFormats(
      catalog.sports.flatMap((sport) =>
        sport.formats.map((format) => ({ ...format, sportName: sport.name })),
      ),
    );
  }

  function applyProfile(loaded: Profile) {
    setProfile(loaded);
    setDisplayName(loaded.display_name ?? '');
    setBio(loaded.bio ?? '');
    const firstSport = loaded.sports[0];
    if (firstSport) {
      setSelectedFormat(firstSport.format_id);
      setLevel(firstSport.level as Level);
      setCourt(firstSport.court_preference as CourtPreference);
    }
    setWindows(
      sortWindows(
        loaded.availability.map((item) => ({
          weekday: item.weekday,
          start: item.start_time.slice(0, 5),
          end: item.end_time.slice(0, 5),
        })),
      ),
    );
  }

  async function run(action: () => Promise<void>, success?: string) {
    setBusy(true);
    try {
      await action();
      if (success) {
        setMessage(success);
      }
    } catch (error) {
      setMessage(describeError(error));
    } finally {
      setBusy(false);
    }
  }

  async function saveBasics() {
    if (!accessToken) {
      return;
    }
    await run(async () => {
      const updated = await profileApi.updateProfile(
        accessToken,
        displayName.trim() || null,
        bio.trim() || null,
      );
      applyProfile(updated);
    }, 'Dados básicos salvos.');
  }

  async function saveSport() {
    if (!accessToken || !selectedFormat) {
      setMessage('Escolha uma modalidade.');
      return;
    }
    await run(async () => {
      const updated = await profileApi.replaceSports(accessToken, [
        {
          format_id: selectedFormat,
          level,
          court_preference: court,
        },
      ]);
      applyProfile(updated);
    }, 'Modalidade salva.');
  }

  function addWindow() {
    const startMinutes = toMinutes(startTime);
    const endMinutes = toMinutes(endTime);
    if (startMinutes === null || endMinutes === null) {
      setMessage('Use horários no formato HH:MM.');
      return;
    }
    if (startMinutes >= endMinutes) {
      setMessage('O horário inicial precisa ser menor que o final.');
      return;
    }
    const overlaps = windows.some((item) => {
      if (item.weekday !== weekday) {
        return false;
      }
      const itemStart = toMinutes(item.start);
      const itemEnd = toMinutes(item.end);
      return (
        itemStart !== null && itemEnd !== null && startMinutes < itemEnd && itemStart < endMinutes
      );
    });
    if (overlaps) {
      setMessage(`Já existe uma faixa que se sobrepõe na ${weekdayLabel(weekday)}.`);
      return;
    }
    setWindows((current) => sortWindows([...current, { weekday, start: startTime, end: endTime }]));
    setMessage('Faixa adicionada à agenda. Salve para gravar.');
  }

  function removeWindow(index: number) {
    setWindows((current) => current.filter((_, position) => position !== index));
  }

  async function saveAvailability() {
    if (!accessToken) {
      return;
    }
    await run(
      async () => {
        const updated = await profileApi.replaceAvailability(
          accessToken,
          windows.map((item) => ({
            weekday: item.weekday,
            start_time: withSeconds(item.start),
            end_time: withSeconds(item.end),
          })),
        );
        applyProfile(updated);
      },
      windows.length === 0 ? 'Agenda esvaziada.' : 'Agenda semanal salva.',
    );
  }

  async function saveCepRegion() {
    if (!accessToken) {
      return;
    }
    const parsedRadius = Number.parseInt(radius, 10);
    await run(async () => {
      const updated = await profileApi.setRegionByCep(
        accessToken,
        cep,
        Number.isFinite(parsedRadius) ? parsedRadius : 10,
      );
      applyProfile(updated);
    }, 'Região por CEP salva.');
  }

  async function useGpsRegion() {
    if (!accessToken) {
      return;
    }
    await run(async () => {
      const permission = await Location.requestForegroundPermissionsAsync();
      if (permission.status !== 'granted') {
        throw new Error('GPS negado. Use o CEP como alternativa manual.');
      }
      const position = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });
      const updated = await profileApi.setRegionByLocation(
        accessToken,
        position.coords.latitude,
        position.coords.longitude,
        Number.parseInt(radius, 10) || 10,
      );
      applyProfile(updated);
    }, 'Região aproximada por GPS salva.');
  }

  async function discover() {
    if (!accessToken) {
      return;
    }
    await run(async () => {
      const page = await profileApi.discoverVenues(accessToken);
      setVenues(page.items);
      setMessage(`${page.total} local(is) encontrado(s) no raio atual.`);
    });
  }

  if (!accessToken) {
    return (
      <View style={styles.container}>
        <Text style={styles.heading}>Perfil e descoberta</Text>
        <View style={styles.card}>
          <Text style={styles.value}>{message}</Text>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.heading}>Perfil e descoberta</Text>
      <Text style={styles.body}>
        Perfil esportivo, disponibilidade e região. O CEP é a alternativa manual ao GPS.
      </Text>

      <View style={styles.card}>
        <Text style={styles.label}>Dados básicos</Text>
        <TextInput
          onChangeText={setDisplayName}
          placeholder="Nome de exibição"
          style={styles.input}
          value={displayName}
        />
        <TextInput
          multiline
          onChangeText={setBio}
          placeholder="Bio curta"
          style={[styles.input, styles.multiline]}
          value={bio}
        />
        <Pressable disabled={busy} onPress={saveBasics} style={styles.button}>
          <Text style={styles.buttonText}>Salvar dados básicos</Text>
        </Pressable>
      </View>

      <View style={styles.card}>
        <Text style={styles.label}>Modalidade e nível</Text>
        <View style={styles.wrap}>
          {formats.map((format) => (
            <Pressable
              key={format.id}
              disabled={busy}
              onPress={() => setSelectedFormat(format.id)}
              style={[styles.chip, selectedFormat === format.id && styles.chipActive]}
            >
              <Text style={selectedFormat === format.id ? styles.chipTextActive : styles.chipText}>
                {format.sportName} · {format.duration_minutes} min
              </Text>
            </Pressable>
          ))}
        </View>
        <View style={styles.wrap}>
          {LEVELS.map((item) => (
            <Pressable
              key={item.value}
              disabled={busy}
              onPress={() => setLevel(item.value)}
              style={[styles.chip, level === item.value && styles.chipActive]}
            >
              <Text style={level === item.value ? styles.chipTextActive : styles.chipText}>
                {item.label}
              </Text>
            </Pressable>
          ))}
        </View>
        <View style={styles.wrap}>
          {COURTS.map((item) => (
            <Pressable
              key={item.value}
              disabled={busy}
              onPress={() => setCourt(item.value)}
              style={[styles.chip, court === item.value && styles.chipActive]}
            >
              <Text style={court === item.value ? styles.chipTextActive : styles.chipText}>
                {item.label}
              </Text>
            </Pressable>
          ))}
        </View>
        <Pressable disabled={busy} onPress={saveSport} style={styles.button}>
          <Text style={styles.buttonText}>Salvar modalidade</Text>
        </Pressable>
      </View>

      <View style={styles.card}>
        <Text style={styles.label}>Disponibilidade semanal</Text>
        <Text style={styles.hint}>
          Monte a agenda: escolha o dia, informe a faixa e adicione quantas quiser. Um dia pode ter
          várias faixas e dias diferentes podem ter horários diferentes.
        </Text>
        <View style={styles.wrap}>
          {WEEKDAYS.map((label, index) => {
            const value = index + 1;
            const count = windows.filter((item) => item.weekday === value).length;
            return (
              <Pressable
                key={label}
                disabled={busy}
                onPress={() => setWeekday(value)}
                style={[styles.chip, weekday === value && styles.chipActive]}
              >
                <Text style={weekday === value ? styles.chipTextActive : styles.chipText}>
                  {count > 0 ? `${label} · ${count}` : label}
                </Text>
              </Pressable>
            );
          })}
        </View>
        <View style={styles.row}>
          <TextInput
            onChangeText={setStartTime}
            placeholder="18:00"
            style={[styles.input, styles.timeInput]}
            value={startTime}
          />
          <Text style={styles.value}>até</Text>
          <TextInput
            onChangeText={setEndTime}
            placeholder="20:00"
            style={[styles.input, styles.timeInput]}
            value={endTime}
          />
        </View>
        <Pressable disabled={busy} onPress={addWindow} style={styles.secondaryButton}>
          <Text style={styles.secondaryButtonText}>Adicionar faixa em {weekdayLabel(weekday)}</Text>
        </Pressable>

        {windows.length === 0 ? (
          <Text style={styles.value}>Nenhuma faixa na agenda.</Text>
        ) : (
          <View style={styles.agendaList}>
            {windows.map((item, index) => (
              <View key={`${item.weekday}-${item.start}-${item.end}`} style={styles.agendaRow}>
                <Text style={styles.agendaDay}>{weekdayLabel(item.weekday)}</Text>
                <Text style={styles.agendaTime}>
                  {item.start} – {item.end}
                </Text>
                <Pressable
                  accessibilityLabel={`Remover ${weekdayLabel(item.weekday)} das ${item.start} às ${item.end}`}
                  disabled={busy}
                  hitSlop={8}
                  onPress={() => removeWindow(index)}
                  style={styles.removeButton}
                >
                  <Text style={styles.removeText}>remover</Text>
                </Pressable>
              </View>
            ))}
          </View>
        )}

        <Pressable disabled={busy} onPress={saveAvailability} style={styles.button}>
          <Text style={styles.buttonText}>Salvar agenda</Text>
        </Pressable>
      </View>

      <View style={styles.card}>
        <Text style={styles.label}>Região de busca</Text>
        <Text style={styles.value}>
          {profile?.region
            ? `${profile.region.city ?? 'GPS'}${profile.region.state ? `/${profile.region.state}` : ''} · ${profile.region.radius_km} km · ${profile.region.source}`
            : 'Nenhuma região definida.'}
        </Text>
        <View style={styles.row}>
          <TextInput
            keyboardType="number-pad"
            onChangeText={setCep}
            placeholder="CEP"
            style={[styles.input, styles.grow]}
            value={cep}
          />
          <TextInput
            keyboardType="number-pad"
            onChangeText={setRadius}
            placeholder="Raio km"
            style={[styles.input, styles.radiusInput]}
            value={radius}
          />
        </View>
        <Pressable disabled={busy} onPress={saveCepRegion} style={styles.button}>
          <Text style={styles.buttonText}>Buscar região por CEP</Text>
        </Pressable>
        <Pressable disabled={busy} onPress={useGpsRegion} style={styles.secondaryButton}>
          <Text style={styles.secondaryButtonText}>Usar localização atual</Text>
        </Pressable>
      </View>

      <View style={styles.card}>
        <Text style={styles.label}>Locais</Text>
        <Pressable disabled={busy} onPress={discover} style={styles.button}>
          <Text style={styles.buttonText}>Descobrir locais</Text>
        </Pressable>
        {venues.length === 0 ? (
          <Text style={styles.value}>Nenhum local no catálogo desta prova.</Text>
        ) : (
          venues.map((venue) => (
            <Text key={venue.id} style={styles.value}>
              {venue.name} · {venue.city}/{venue.state}
            </Text>
          ))
        )}
      </View>

      <View style={styles.card}>
        <Text style={styles.label}>Resultado</Text>
        <Text accessibilityLiveRegion="polite" style={styles.value}>
          {message}
        </Text>
        {busy ? <ActivityIndicator color="#26724a" /> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: 14 },
  heading: { color: '#173b2a', fontSize: 21, fontWeight: '700' },
  body: { color: '#52625a', fontSize: 15, lineHeight: 22 },
  card: { backgroundColor: '#fff', borderRadius: 14, padding: 16, gap: 10 },
  label: { color: '#52625a', fontSize: 12, fontWeight: '700', textTransform: 'uppercase' },
  value: { color: '#173b2a', fontSize: 14, lineHeight: 20 },
  hint: { color: '#66736b', fontSize: 13, lineHeight: 19 },
  agendaList: { gap: 6 },
  agendaRow: {
    alignItems: 'center',
    backgroundColor: '#f4f7f5',
    borderRadius: 10,
    flexDirection: 'row',
    gap: 10,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  agendaDay: { color: '#173b2a', fontSize: 14, fontWeight: '700', width: 46 },
  agendaTime: { color: '#173b2a', flex: 1, fontSize: 14 },
  removeButton: { paddingHorizontal: 6, paddingVertical: 2 },
  removeText: { color: '#a13737', fontSize: 12, fontWeight: '700' },
  input: {
    backgroundColor: '#f4f7f5',
    borderColor: '#d7e3db',
    borderRadius: 10,
    borderWidth: 1,
    color: '#173b2a',
    fontSize: 15,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  multiline: { minHeight: 64, textAlignVertical: 'top' },
  row: { alignItems: 'center', flexDirection: 'row', gap: 8 },
  grow: { flex: 1 },
  timeInput: { flex: 1 },
  radiusInput: { width: 90 },
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: {
    borderColor: '#26724a',
    borderRadius: 999,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 7,
  },
  chipActive: { backgroundColor: '#26724a' },
  chipText: { color: '#26724a', fontWeight: '700' },
  chipTextActive: { color: '#fff', fontWeight: '700' },
  button: {
    alignItems: 'center',
    backgroundColor: '#26724a',
    borderRadius: 12,
    justifyContent: 'center',
    minHeight: 48,
    padding: 12,
  },
  buttonText: { color: '#fff', fontSize: 15, fontWeight: '700', textAlign: 'center' },
  secondaryButton: {
    alignItems: 'center',
    borderColor: '#26724a',
    borderRadius: 12,
    borderWidth: 1,
    justifyContent: 'center',
    minHeight: 46,
    padding: 12,
  },
  secondaryButtonText: { color: '#26724a', fontSize: 15, fontWeight: '700' },
});
