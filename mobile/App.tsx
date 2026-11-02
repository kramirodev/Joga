import { useEffect, useState } from 'react';
import { StatusBar } from 'expo-status-bar';
import * as Location from 'expo-location';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

function describePermission(permission: Location.LocationPermissionResponse): string {
  if (permission.status !== 'granted') {
    return permission.canAskAgain
      ? 'Localização não autorizada. O app pode solicitar novamente.'
      : 'Localização negada. Altere a permissão nas configurações do Android.';
  }

  const precision = permission.android?.accuracy ?? permission.ios?.accuracy;
  return precision
    ? `Autorizada em primeiro plano • precisão ${precision}`
    : 'Autorizada em primeiro plano';
}

export default function App() {
  const [permissionMessage, setPermissionMessage] = useState('Consultando permissão…');
  const [locationMessage, setLocationMessage] = useState('Nenhuma leitura de localização realizada.');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void Location.getForegroundPermissionsAsync()
      .then((permission) => setPermissionMessage(describePermission(permission)))
      .catch(() => setPermissionMessage('Não foi possível consultar a permissão.'));
  }, []);

  async function requestForegroundPermission() {
    setBusy(true);
    try {
      const permission = await Location.requestForegroundPermissionsAsync();
      setPermissionMessage(describePermission(permission));
      setLocationMessage('Nenhuma leitura de localização realizada.');
    } catch {
      setPermissionMessage('Não foi possível solicitar a permissão.');
    } finally {
      setBusy(false);
    }
  }

  async function readLocationOnce() {
    setBusy(true);
    try {
      const permission = await Location.getForegroundPermissionsAsync();
      setPermissionMessage(describePermission(permission));
      if (permission.status !== 'granted') {
        setLocationMessage('Autorize a localização em primeiro plano para executar esta leitura.');
        return;
      }

      const location = await Location.getCurrentPositionAsync({
        accuracy: Location.LocationAccuracy.Balanced,
        mayShowUserSettingsDialog: false,
      });
      const accuracy = location.coords.accuracy;
      setLocationMessage(
        `Leitura única concluída${accuracy === null ? '' : ` • precisão estimada de ${Math.round(accuracy)} m`}. Coordenadas não exibidas nem armazenadas.`,
      );
    } catch {
      setLocationMessage('A leitura não foi concluída. Verifique se os serviços de localização estão ativos.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.eyebrow}>PROVA TÉCNICA • FASE 1</Text>
      <Text style={styles.title}>JOGA</Text>
      <Text style={styles.heading}>Permissão de localização</Text>
      <Text style={styles.body}>
        Este teste solicita acesso somente enquanto o app está em uso. Nenhuma coordenada é salva.
      </Text>

      <View style={styles.card}>
        <Text style={styles.label}>Estado da permissão</Text>
        <Text accessibilityLiveRegion="polite" style={styles.value}>{permissionMessage}</Text>
      </View>

      <Pressable
        accessibilityRole="button"
        disabled={busy}
        onPress={requestForegroundPermission}
        style={({ pressed }) => [styles.button, pressed && styles.buttonPressed, busy && styles.buttonDisabled]}
      >
        {busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Solicitar permissão em primeiro plano</Text>}
      </Pressable>

      <Pressable
        accessibilityRole="button"
        disabled={busy}
        onPress={readLocationOnce}
        style={({ pressed }) => [styles.secondaryButton, pressed && styles.buttonPressed, busy && styles.buttonDisabled]}
      >
        <Text style={styles.secondaryButtonText}>Fazer uma leitura única</Text>
      </Pressable>

      <View style={styles.card}>
        <Text style={styles.label}>Resultado</Text>
        <Text accessibilityLiveRegion="polite" style={styles.value}>{locationMessage}</Text>
      </View>

      <Text style={styles.footnote}>
        Para repetir a prova com outra permissão, altere a localização do app JOGA nas configurações do Android.
      </Text>
      <StatusBar style="auto" />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f4f7f5',
    justifyContent: 'center',
    paddingHorizontal: 24,
    paddingVertical: 32,
    gap: 14,
  },
  eyebrow: { color: '#26724a', fontSize: 12, fontWeight: '700', letterSpacing: 1.2 },
  title: { color: '#173b2a', fontSize: 38, fontWeight: '800' },
  heading: { color: '#173b2a', fontSize: 21, fontWeight: '700' },
  body: { color: '#52625a', fontSize: 15, lineHeight: 22 },
  card: { backgroundColor: '#fff', borderRadius: 14, padding: 16, gap: 6 },
  label: { color: '#52625a', fontSize: 12, fontWeight: '700', textTransform: 'uppercase' },
  value: { color: '#173b2a', fontSize: 15, lineHeight: 22 },
  button: { alignItems: 'center', backgroundColor: '#26724a', borderRadius: 12, minHeight: 52, justifyContent: 'center', padding: 14 },
  buttonPressed: { opacity: 0.82 },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { color: '#fff', fontSize: 15, fontWeight: '700', textAlign: 'center' },
  secondaryButton: { alignItems: 'center', borderColor: '#26724a', borderRadius: 12, borderWidth: 1, minHeight: 50, justifyContent: 'center', padding: 14 },
  secondaryButtonText: { color: '#26724a', fontSize: 15, fontWeight: '700' },
  footnote: { color: '#66736b', fontSize: 12, lineHeight: 18 },
});
