import { useEffect, useState } from 'react';
import { StatusBar } from 'expo-status-bar';
import * as Location from 'expo-location';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import PasskeyProof from './modules/passkey-proof';
import { IdentityPanel } from './src/IdentityPanel';
import { ProfilePanel } from './src/ProfilePanel';

const RP_ID = 'joga-passkeys.vercel.app';
const RP_NAME = 'JOGA (prova técnica)';
const PASSKEY_USER = 'prova-joga';

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

function describeError(error: unknown): string {
  if (error instanceof Error && error.message.trim().length > 0) {
    return error.message;
  }
  return 'Falha desconhecida durante a cerimônia de passkey.';
}

export default function App() {
  const [permissionMessage, setPermissionMessage] = useState('Consultando permissão…');
  const [locationMessage, setLocationMessage] = useState(
    'Nenhuma leitura de localização realizada.',
  );
  const [busy, setBusy] = useState(false);
  const platformSummary = PasskeyProof
    ? PasskeyProof.getPlatformSummary()
    : 'Módulo nativo de passkey indisponível.';
  const [passkeyMessage, setPasskeyMessage] = useState(
    'Nenhuma cerimônia de passkey executada nesta instalação.',
  );
  const [passkeyDetail, setPasskeyDetail] = useState('');
  const [credentialId, setCredentialId] = useState('');
  const [passkeyBusy, setPasskeyBusy] = useState(false);

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
        accuracy: Location.Accuracy.Balanced,
        mayShowUserSettingsDialog: false,
      });
      const accuracy = location.coords.accuracy;
      setLocationMessage(
        `Leitura única concluída${accuracy === null ? '' : ` • precisão estimada de ${Math.round(accuracy)} m`}. Coordenadas não exibidas nem armazenadas.`,
      );
    } catch {
      setLocationMessage(
        'A leitura não foi concluída. Verifique se os serviços de localização estão ativos.',
      );
    } finally {
      setBusy(false);
    }
  }

  async function createPasskey() {
    if (!PasskeyProof) {
      setPasskeyMessage('O módulo nativo de passkey não está presente neste build.');
      return;
    }

    setPasskeyBusy(true);
    setPasskeyMessage('Abrindo o Credential Manager para criar a passkey…');
    setPasskeyDetail('');
    try {
      const result = await PasskeyProof.createPasskeyAsync(RP_ID, RP_NAME, PASSKEY_USER);
      setCredentialId(result.credentialId);
      setPasskeyMessage('Passkey criada e registrada pelo Google Password Manager.');
      setPasskeyDetail(
        [
          `clientData.type: ${result.clientDataType}`,
          `clientData.origin: ${result.clientDataOrigin}`,
          `credentialId: ${result.credentialId}`,
        ].join('\n'),
      );
    } catch (error) {
      setPasskeyMessage(describeError(error));
      setPasskeyDetail('');
    } finally {
      setPasskeyBusy(false);
    }
  }

  async function getPasskey() {
    if (!PasskeyProof) {
      setPasskeyMessage('O módulo nativo de passkey não está presente neste build.');
      return;
    }

    setPasskeyBusy(true);
    setPasskeyMessage('Abrindo o seletor de passkeys do sistema…');
    setPasskeyDetail('');
    try {
      const result = await PasskeyProof.getPasskeyAsync(RP_ID, credentialId);
      const sameCredential =
        credentialId.length === 0 || credentialId === result.credentialId
          ? 'sim'
          : 'não (outra credencial foi escolhida)';
      setPasskeyMessage(
        result.rpIdHashMatches
          ? 'Autenticação concluída: rpIdHash confere com o RP ID solicitado.'
          : 'Autenticação retornou credencial, mas o rpIdHash NÃO confere.',
      );
      setPasskeyDetail(
        [
          `clientData.type: ${result.clientDataType}`,
          `clientData.origin: ${result.clientDataOrigin}`,
          `credentialId: ${result.credentialId}`,
          `Mesma credencial criada nesta sessão: ${sameCredential}`,
          `rpIdHashMatches: ${result.rpIdHashMatches}`,
          `userPresent: ${result.userPresent}`,
          `userVerified: ${result.userVerified}`,
        ].join('\n'),
      );
    } catch (error) {
      setPasskeyMessage(describeError(error));
      setPasskeyDetail('');
    } finally {
      setPasskeyBusy(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.eyebrow}>PROVA TÉCNICA • FASE 1</Text>
      <Text style={styles.title}>JOGA</Text>
      <Text style={styles.heading}>Permissão de localização</Text>
      <Text style={styles.body}>
        Este teste solicita acesso somente enquanto o app está em uso. Nenhuma coordenada é salva.
      </Text>

      <View style={styles.card}>
        <Text style={styles.label}>Estado da permissão</Text>
        <Text accessibilityLiveRegion="polite" style={styles.value}>
          {permissionMessage}
        </Text>
      </View>

      <Pressable
        accessibilityRole="button"
        disabled={busy}
        onPress={requestForegroundPermission}
        style={({ pressed }) => [
          styles.button,
          pressed && styles.buttonPressed,
          busy && styles.buttonDisabled,
        ]}
      >
        {busy ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.buttonText}>Solicitar permissão em primeiro plano</Text>
        )}
      </Pressable>

      <Pressable
        accessibilityRole="button"
        disabled={busy}
        onPress={readLocationOnce}
        style={({ pressed }) => [
          styles.secondaryButton,
          pressed && styles.buttonPressed,
          busy && styles.buttonDisabled,
        ]}
      >
        <Text style={styles.secondaryButtonText}>Fazer uma leitura única</Text>
      </Pressable>

      <View style={styles.card}>
        <Text style={styles.label}>Resultado</Text>
        <Text accessibilityLiveRegion="polite" style={styles.value}>
          {locationMessage}
        </Text>
      </View>

      <View style={styles.divider} />

      <Text style={styles.heading}>Passkey (Android)</Text>
      <Text style={styles.body}>
        Cria e usa uma passkey local com o Credential Manager. A associação do RP ID é verificada
        pelo Android contra o assetlinks.json publicado; não há backend nesta prova.
      </Text>

      <View style={styles.card}>
        <Text style={styles.label}>Ambiente</Text>
        <Text style={styles.value}>{platformSummary}</Text>
        <Text style={styles.mono}>RP ID: {RP_ID}</Text>
      </View>

      <Pressable
        accessibilityRole="button"
        disabled={passkeyBusy}
        onPress={createPasskey}
        style={({ pressed }) => [
          styles.button,
          pressed && styles.buttonPressed,
          passkeyBusy && styles.buttonDisabled,
        ]}
      >
        {passkeyBusy ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.buttonText}>Criar passkey</Text>
        )}
      </Pressable>

      <Pressable
        accessibilityRole="button"
        disabled={passkeyBusy}
        onPress={getPasskey}
        style={({ pressed }) => [
          styles.secondaryButton,
          pressed && styles.buttonPressed,
          passkeyBusy && styles.buttonDisabled,
        ]}
      >
        <Text style={styles.secondaryButtonText}>Entrar com passkey</Text>
      </Pressable>

      <View style={styles.card}>
        <Text style={styles.label}>Resultado da passkey</Text>
        <Text accessibilityLiveRegion="polite" style={styles.value}>
          {passkeyMessage}
        </Text>
        {passkeyDetail.length > 0 ? (
          <Text selectable style={styles.mono}>
            {passkeyDetail}
          </Text>
        ) : null}
      </View>

      <View style={styles.divider} />

      <IdentityPanel />

      <View style={styles.divider} />

      <ProfilePanel />

      <View style={styles.divider} />

      <Text style={styles.footnote}>
        Para repetir a prova de localização com outra permissão, altere a localização do app JOGA
        nas configurações do Android. Se a passkey já existir, use “Entrar com passkey”. Remova a
        credencial pelo Google Password Manager para repetir a criação.
      </Text>
      <StatusBar style="auto" />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flexGrow: 1,
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
  mono: { color: '#173b2a', fontFamily: 'monospace', fontSize: 12, lineHeight: 18 },
  divider: { backgroundColor: '#d7e3db', height: 1, marginVertical: 6 },
  button: {
    alignItems: 'center',
    backgroundColor: '#26724a',
    borderRadius: 12,
    minHeight: 52,
    justifyContent: 'center',
    padding: 14,
  },
  buttonPressed: { opacity: 0.82 },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { color: '#fff', fontSize: 15, fontWeight: '700', textAlign: 'center' },
  secondaryButton: {
    alignItems: 'center',
    borderColor: '#26724a',
    borderRadius: 12,
    borderWidth: 1,
    minHeight: 50,
    justifyContent: 'center',
    padding: 14,
  },
  secondaryButtonText: { color: '#26724a', fontSize: 15, fontWeight: '700' },
  footnote: { color: '#66736b', fontSize: 12, lineHeight: 18 },
});
