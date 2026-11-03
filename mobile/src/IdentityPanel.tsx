import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import PasskeyProof from '../modules/passkey-proof';
import { ApiError, identityApi, type DeviceInfo, type PasskeySummary, type Tokens } from './api';
import { clearSession, loadSession, saveSession, type StoredSession } from './session';

const DEVICE: DeviceInfo = {
  name: 'JOGA prova',
  platform: Platform.OS === 'android' || Platform.OS === 'ios' ? Platform.OS : 'unknown',
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

export function IdentityPanel() {
  const [phone, setPhone] = useState('+5511999999999');
  const [purpose, setPurpose] = useState<'registration' | 'login'>('registration');
  const [challengeId, setChallengeId] = useState('');
  const [code, setCode] = useState('');
  const [session, setSession] = useState<StoredSession | null>(null);
  const [passkeys, setPasskeys] = useState<PasskeySummary[]>([]);
  const [newPhone, setNewPhone] = useState('');
  const [changeChallengeId, setChangeChallengeId] = useState('');
  const [changeCode, setChangeCode] = useState('');
  const [message, setMessage] = useState('Informe o telefone para começar.');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    void (async () => {
      const stored = await loadSession();
      if (!active || !stored) {
        return;
      }
      try {
        const me = await identityApi.me(stored.accessToken);
        if (active) {
          setSession({ ...stored, userId: me.id, userStatus: me.status });
          setMessage(`Sessão ativa para ${me.id}.`);
        }
      } catch {
        await clearSession();
        if (active) {
          setSession(null);
          setMessage('A sessão anterior expirou. Entre novamente.');
        }
      }
    })();
    return () => {
      active = false;
    };
  }, []);

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

  async function sendCode() {
    await run(async () => {
      const challenge = await identityApi.requestChallenge(phone, purpose);
      setChallengeId(challenge.challenge_id);
      setCode('');
    }, 'Código enviado. Informe o código de seis dígitos.');
  }

  async function verifyAndContinue() {
    await run(async () => {
      const verified = await identityApi.verifyChallenge(challengeId, code);
      const tokens: Tokens =
        purpose === 'registration'
          ? await identityApi.register(verified.challenge_id, DEVICE)
          : await identityApi.login(verified.challenge_id, DEVICE);
      const stored = await saveSession(tokens);
      setSession(stored);
      setPhone(phone);
      setMessage(
        purpose === 'registration' ? 'Conta criada e sessão iniciada.' : 'Login concluído.',
      );
    });
  }

  async function addPasskey() {
    await run(async () => {
      if (!PasskeyProof) {
        throw new Error('Módulo nativo de passkey indisponível neste build.');
      }
      if (!session) {
        throw new Error('Entre na conta antes de adicionar uma passkey.');
      }
      const options = await identityApi.passkeyRegistrationOptions(session.accessToken);
      const result = await PasskeyProof.createPasskeyFromRequestAsync(
        JSON.stringify(options.public_key),
      );
      await identityApi.passkeyRegistrationVerify(
        session.accessToken,
        options.challenge_id,
        JSON.parse(result.registrationResponseJson) as unknown,
      );
      const list = await identityApi.passkeys(session.accessToken);
      setPasskeys(list.credentials);
    }, 'Passkey adicionada à conta.');
  }

  async function loginWithPasskey() {
    await run(async () => {
      if (!PasskeyProof) {
        throw new Error('Módulo nativo de passkey indisponível neste build.');
      }
      const options = await identityApi.passkeyAuthenticationOptions();
      const result = await PasskeyProof.getPasskeyFromRequestAsync(
        JSON.stringify(options.public_key),
      );
      const tokens = await identityApi.passkeyAuthenticationVerify(
        options.challenge_id,
        JSON.parse(result.authenticationResponseJson) as unknown,
        DEVICE,
      );
      const stored = await saveSession(tokens);
      setSession(stored);
      setPhone(phone);
    }, 'Login com passkey concluído.');
  }

  async function listPasskeys() {
    await run(async () => {
      if (!session) {
        throw new Error('Entre na conta primeiro.');
      }
      const list = await identityApi.passkeys(session.accessToken);
      setPasskeys(list.credentials);
    }, 'Passkeys atualizadas.');
  }

  async function logout() {
    await run(async () => {
      if (session) {
        await identityApi.logout(session.accessToken);
      }
      await clearSession();
      setSession(null);
      setPasskeys([]);
    }, 'Sessão encerrada.');
  }

  async function requestPhoneChange() {
    await run(async () => {
      if (!session) {
        throw new Error('Entre na conta primeiro.');
      }
      const challenge = await identityApi.phoneChangeChallenge(session.accessToken, newPhone);
      setChangeChallengeId(challenge.challenge_id);
      setChangeCode('');
    }, 'Código enviado ao novo telefone.');
  }

  async function confirmPhoneChange() {
    await run(async () => {
      if (!session) {
        throw new Error('Entre na conta primeiro.');
      }
      await identityApi.phoneChangeConfirm(session.accessToken, changeChallengeId, changeCode);
      await clearSession();
      setSession(null);
      setPasskeys([]);
      setChangeChallengeId('');
    }, 'Telefone trocado. Entre novamente com o novo número.');
  }

  return (
    <View style={styles.container}>
      <Text style={styles.heading}>Conta e sessão</Text>
      <Text style={styles.body}>
        Cadastro e login por telefone/OTP, passkey e sessão. Em desenvolvimento local, o backend
        pode usar um OTP fixo configurado fora do app.
      </Text>

      <View style={styles.card}>
        <Text style={styles.label}>Telefone (E.164)</Text>
        <TextInput
          autoCapitalize="none"
          keyboardType="phone-pad"
          onChangeText={setPhone}
          placeholder="+5511999999999"
          style={styles.input}
          value={phone}
        />
        <View style={styles.row}>
          <Pressable
            disabled={busy}
            onPress={() => setPurpose('registration')}
            style={[styles.chip, purpose === 'registration' && styles.chipActive]}
          >
            <Text style={purpose === 'registration' ? styles.chipTextActive : styles.chipText}>
              Registrar
            </Text>
          </Pressable>
          <Pressable
            disabled={busy}
            onPress={() => setPurpose('login')}
            style={[styles.chip, purpose === 'login' && styles.chipActive]}
          >
            <Text style={purpose === 'login' ? styles.chipTextActive : styles.chipText}>
              Entrar
            </Text>
          </Pressable>
        </View>
        <Pressable disabled={busy} onPress={sendCode} style={styles.button}>
          <Text style={styles.buttonText}>Enviar código</Text>
        </Pressable>
      </View>

      <View style={styles.card}>
        <Text style={styles.label}>Código OTP</Text>
        <TextInput
          keyboardType="number-pad"
          maxLength={6}
          onChangeText={setCode}
          placeholder="123456"
          style={styles.input}
          value={code}
        />
        <Pressable
          disabled={busy || challengeId.length === 0 || code.length !== 6}
          onPress={verifyAndContinue}
          style={[styles.button, (busy || code.length !== 6) && styles.disabled]}
        >
          <Text style={styles.buttonText}>
            {purpose === 'registration' ? 'Verificar e criar conta' : 'Verificar e entrar'}
          </Text>
        </Pressable>
      </View>

      {session ? (
        <View style={styles.card}>
          <Text style={styles.label}>Sessão ativa</Text>
          <Text style={styles.value}>Usuário: {session.userId}</Text>
          <Text style={styles.value}>Status: {session.userStatus}</Text>
          <Text style={styles.value}>Passkeys: {passkeys.length}</Text>
          <Pressable disabled={busy} onPress={addPasskey} style={styles.button}>
            <Text style={styles.buttonText}>Adicionar passkey</Text>
          </Pressable>
          <Pressable disabled={busy} onPress={listPasskeys} style={styles.secondaryButton}>
            <Text style={styles.secondaryButtonText}>Atualizar passkeys</Text>
          </Pressable>
          <Pressable disabled={busy} onPress={logout} style={styles.secondaryButton}>
            <Text style={styles.secondaryButtonText}>Sair</Text>
          </Pressable>
        </View>
      ) : null}

      <Pressable disabled={busy} onPress={loginWithPasskey} style={styles.secondaryButton}>
        <Text style={styles.secondaryButtonText}>Entrar com passkey</Text>
      </Pressable>

      {session ? (
        <View style={styles.card}>
          <Text style={styles.label}>Trocar telefone</Text>
          <TextInput
            autoCapitalize="none"
            keyboardType="phone-pad"
            onChangeText={setNewPhone}
            placeholder="+5511988887777"
            style={styles.input}
            value={newPhone}
          />
          <Pressable
            disabled={busy || newPhone.length < 7}
            onPress={requestPhoneChange}
            style={[styles.button, (busy || newPhone.length < 7) && styles.disabled]}
          >
            <Text style={styles.buttonText}>Solicitar troca</Text>
          </Pressable>
          {changeChallengeId ? (
            <>
              <TextInput
                keyboardType="number-pad"
                maxLength={6}
                onChangeText={setChangeCode}
                placeholder="Código no novo telefone"
                style={styles.input}
                value={changeCode}
              />
              <Pressable
                disabled={busy || changeCode.length !== 6}
                onPress={confirmPhoneChange}
                style={[styles.button, (busy || changeCode.length !== 6) && styles.disabled]}
              >
                <Text style={styles.buttonText}>Confirmar troca</Text>
              </Pressable>
            </>
          ) : null}
        </View>
      ) : null}

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
  row: { flexDirection: 'row', gap: 10 },
  chip: {
    borderColor: '#26724a',
    borderRadius: 999,
    borderWidth: 1,
    paddingHorizontal: 16,
    paddingVertical: 8,
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
  disabled: { opacity: 0.55 },
});
