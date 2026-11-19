import { useEffect, useRef, useState, type ElementRef } from 'react';
import { Platform, TextInput, View } from 'react-native';

import { api, ApiError } from '../api/client';
import type { EmailCredential, Tokens } from '../api/types';
import { authConfig } from '../auth/config';
import { createPasskey, passkeyAvailable } from '../passkey';
import { useApp } from '../state/app';
import { useNav, useTheme } from '../state/context';
import {
  Badge,
  Btn,
  Card,
  CardList,
  Check,
  EmptyState,
  Field,
  Input,
  ListRow,
  LoadingState,
  Notice,
  Page,
  Row,
  StateScreen,
  TextBtn,
  Txt,
} from '../ui/kit';
import { Text } from '../ui/text';
import type { ScreenDef } from './types';

type EmailPurpose = 'registration' | 'password_reset';

type EmailErrorInfo = { message: string; unavailable: boolean };

function deviceInfo() {
  const platform: 'android' | 'ios' | 'unknown' =
    Platform.OS === 'ios' ? 'ios' : Platform.OS === 'android' ? 'android' : 'unknown';
  return {
    name: platform === 'ios' ? 'iPhone' : platform === 'android' ? 'Android' : 'JOGA',
    platform,
  };
}

function emailError(error: unknown): EmailErrorInfo {
  if (!(error instanceof ApiError)) {
    return { message: 'Não foi possível concluir a ação.', unavailable: false };
  }
  const messages: Record<string, string> = {
    network_unavailable: 'Não foi possível falar com o servidor.',
    request_timeout: 'O servidor demorou para responder. Tente novamente.',
    invalid_email: 'Informe um e-mail válido.',
    email_domain_not_allowed: 'Este domínio de e-mail não é aceito.',
    invalid_code_or_challenge: 'Código inválido ou expirado.',
    invalid_receipt: 'A verificação expirou. Recomece o fluxo.',
    invalid_email_login: 'E-mail ou senha inválidos.',
    invalid_credentials: 'E-mail ou senha inválidos.',
    invalid_password: 'Senha inválida.',
    invalid_current_password: 'Senha atual inválida.',
    password_too_short: 'A senha é curta demais.',
    signup_closed: 'O cadastro está fechado neste beta.',
    email_registration_disabled: 'O cadastro por e-mail está indisponível nesta versão.',
    phone_registration_disabled: 'O cadastro por telefone está indisponível nesta versão.',
    phone_required: 'Esta ação exige telefone verificado no lançamento.',
    email_already_registered: 'Este e-mail já está vinculado a uma conta ativa.',
    rate_limited: 'Muitas tentativas. Aguarde para pedir outro código.',
    email_change_cooldown: 'Já houve uma troca recente. Aguarde o prazo para tentar de novo.',
    invalid_email_change: 'Código inválido ou expirado.',
    email_unchanged: 'O novo e-mail é igual ao atual.',
    email_auth_disabled: 'O login por e-mail está indisponível nesta versão.',
    phone_auth_disabled: 'O login por telefone está indisponível nesta versão.',
  };
  return {
    message: messages[error.code] ?? 'Não foi possível concluir a ação.',
    unavailable: error.status === 503,
  };
}

function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) {
      return;
    }
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [active]);
  return now;
}

function secondsUntil(iso: string | null): number | null {
  if (!iso) {
    return null;
  }
  const target = new Date(iso).getTime();
  if (Number.isNaN(target)) {
    return null;
  }
  return Math.max(0, Math.ceil((target - Date.now()) / 1000));
}

function formatCountdown(seconds: number): string {
  const safe = Math.max(0, seconds);
  return `${Math.floor(safe / 60)}:${String(safe % 60).padStart(2, '0')}`;
}

function CodeInput({
  value,
  onChange,
  onComplete,
}: {
  value: string;
  onChange: (value: string) => void;
  onComplete: () => void;
}) {
  const { palette } = useTheme();
  const [focused, setFocused] = useState(false);
  const inputRef = useRef<ElementRef<typeof TextInput>>(null);
  return (
    <View style={{ position: 'relative' }}>
      <View style={{ flexDirection: 'row', justifyContent: 'center', gap: 8 }}>
        {Array.from({ length: 6 }, (_, index) => {
          const digit = value[index] ?? '';
          const active = focused && index === Math.min(value.length, 5);
          return (
            <View
              key={index}
              style={{
                flex: 1,
                maxWidth: 52,
                height: 56,
                borderRadius: 12,
                borderWidth: active ? 2 : 1.5,
                borderColor: active ? palette.ink : palette.lineStrong,
                backgroundColor: palette.surface,
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Text
                maxFontSizeMultiplier={1.2}
                style={{
                  fontSize: 24,
                  lineHeight: 28,
                  fontWeight: '900',
                  color: digit ? palette.ink : palette.muted,
                }}
              >
                {digit || '·'}
              </Text>
            </View>
          );
        })}
      </View>
      <TextInput
        ref={inputRef}
        value={value}
        onChangeText={(next) => onChange(next.replace(/\D/g, '').slice(0, 6))}
        keyboardType="number-pad"
        textContentType="oneTimeCode"
        autoComplete="one-time-code"
        maxLength={6}
        autoFocus
        caretHidden
        accessibilityLabel="Código de verificação de 6 dígitos"
        returnKeyType="done"
        onSubmitEditing={onComplete}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: 0,
          bottom: 0,
          opacity: 0.02,
          color: 'transparent',
          fontSize: 1,
        }}
      />
    </View>
  );
}

function PasswordInput({
  label,
  value,
  onChangeText,
  placeholder,
  autoComplete,
  textContentType,
}: {
  label: string;
  value: string;
  onChangeText: (value: string) => void;
  placeholder: string;
  autoComplete: 'current-password' | 'new-password';
  textContentType: 'password' | 'newPassword';
}) {
  const [visible, setVisible] = useState(false);
  return (
    <Field label={label}>
      <Input
        value={value}
        onChangeText={onChangeText}
        secureTextEntry={!visible}
        autoCapitalize="none"
        autoCorrect={false}
        autoComplete={autoComplete}
        textContentType={textContentType}
        maxLength={128}
        placeholder={placeholder}
        accessibilityLabel={label}
      />
      <TextBtn muted onPress={() => setVisible((current) => !current)}>
        {visible ? 'Ocultar senha' : 'Mostrar senha'}
      </TextBtn>
    </Field>
  );
}

function PasswordHint({ password }: { password: string }) {
  if (!password || password.length >= 10) {
    return null;
  }
  return (
    <Notice tone="orange" icon="info">
      A senha é curta. Use pelo menos 10 caracteres. O aviso não bloqueia o envio.
    </Notice>
  );
}

function EmailEntry() {
  const nav = useNav();
  const { palette } = useTheme();
  const { auth, setAuth } = useApp();
  const [email, setEmail] = useState(auth.email);
  const [accepted, setAccepted] = useState(true);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<EmailErrorInfo | null>(null);
  const [cooldownUntil, setCooldownUntil] = useState(0);
  const now = useNow(cooldownUntil > 0);
  const cooldownRemaining = Math.max(0, Math.ceil((cooldownUntil - now) / 1000));

  const request = async () => {
    const normalized = email.trim();
    if (!normalized) {
      setFeedback({ message: 'Informe seu e-mail.', unavailable: false });
      return;
    }
    if (!accepted) {
      setFeedback({ message: 'Aceite os termos para continuar.', unavailable: false });
      return;
    }
    setBusy(true);
    setFeedback(null);
    try {
      const challenge = await api.auth.emailRequestCode(normalized, 'registration');
      setAuth({ purpose: 'registration', email: normalized, challengeId: challenge.challenge_id });
      nav.go('email-code', {
        email: normalized,
        purpose: 'registration',
        challengeId: challenge.challenge_id,
        expiresAt: challenge.expires_at,
        resendAfter: challenge.resend_after_seconds,
      });
    } catch (error) {
      setFeedback(emailError(error));
      if (error instanceof ApiError && error.retryAfterSeconds != null) {
        setCooldownUntil(Date.now() + error.retryAfterSeconds * 1000);
      }
    } finally {
      setBusy(false);
    }
  };

  if (feedback?.unavailable) {
    return (
      <Page title="Criar conta">
        <StateScreen
          icon="mail"
          title="E-mail indisponível nesta versão"
          text="O cadastro por e-mail está desligado no servidor. Tente novamente quando o método estiver disponível."
          actions={
            <>
              <Btn tone="primary" go="login">
                Já tenho conta
              </Btn>
              <Btn tone="ghost" go="welcome">
                Voltar
              </Btn>
            </>
          }
        />
      </Page>
    );
  }

  return (
    <Page title="Criar conta">
      <Txt variant="lead">
        Vamos confirmar seu e-mail com um código de 6 dígitos. Depois você define sua senha e o nome
        de exibição.
      </Txt>
      <Field label="E-mail">
        <Input
          value={email}
          onChangeText={setEmail}
          keyboardType="email-address"
          autoCapitalize="none"
          autoCorrect={false}
          autoComplete="email"
          textContentType="emailAddress"
          maxLength={254}
          placeholder="voce@exemplo.com"
        />
      </Field>
      <Check checked={accepted} onChange={setAccepted}>
        Aceito os <Text style={{ fontWeight: '800', color: palette.ink }}>Termos de uso</Text> e a{' '}
        <Text style={{ fontWeight: '800', color: palette.ink }}>Política de privacidade</Text>.
      </Check>
      <TextBtn muted onPress={() => nav.go('terms', { readOnly: 1 })}>
        Ler termos de uso e política de privacidade
      </TextBtn>
      {feedback ? (
        <Notice tone="orange" icon="alert">
          {feedback.message}
        </Notice>
      ) : null}
      <Btn
        tone="primary"
        onPress={request}
        disabled={busy || cooldownRemaining > 0 || !email.trim()}
      >
        {busy
          ? 'Solicitando…'
          : cooldownRemaining > 0
            ? `Aguarde ${cooldownRemaining}s`
            : 'Receber código'}
      </Btn>
      <Notice tone="blue" icon="info">
        A entrega é assíncrona: o código pode levar alguns minutos. Não feche esta tela.
      </Notice>
      <TextBtn
        muted
        onPress={() => {
          setAuth({ purpose: 'login' });
          nav.replace('login-email');
        }}
      >
        Já tenho conta
      </TextBtn>
      {authConfig.phoneEnabled ? (
        <TextBtn
          muted
          onPress={() => {
            setAuth({ purpose: 'registration' });
            nav.go('signup-phone');
          }}
        >
          Usar telefone
        </TextBtn>
      ) : null}
    </Page>
  );
}

function EmailCode() {
  const nav = useNav();
  const { palette } = useTheme();
  const { setAuth } = useApp();
  const email = typeof nav.params.email === 'string' ? nav.params.email : '';
  const purpose: EmailPurpose =
    nav.params.purpose === 'password_reset' ? 'password_reset' : 'registration';
  const initialChallenge =
    typeof nav.params.challengeId === 'string' ? nav.params.challengeId : null;
  const initialExpires = typeof nav.params.expiresAt === 'string' ? nav.params.expiresAt : null;
  const initialResend = typeof nav.params.resendAfter === 'number' ? nav.params.resendAfter : 60;
  const [challengeId, setChallengeId] = useState(initialChallenge);
  const [expiresAt, setExpiresAt] = useState(initialExpires);
  const [resendAt, setResendAt] = useState(() => Date.now() + initialResend * 1000);
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [resending, setResending] = useState(false);
  const [feedback, setFeedback] = useState<EmailErrorInfo | null>(null);
  const [deliveryNotice, setDeliveryNotice] = useState(
    'Enviamos o código. A entrega pode levar alguns minutos.',
  );
  const now = useNow(true);
  const resendRemaining = Math.max(0, Math.ceil((resendAt - now) / 1000));
  const expiresRemaining = secondsUntil(expiresAt);
  const canResend = !resending && resendRemaining === 0;

  if (!challengeId || !email) {
    return (
      <Page title="Digite o código">
        <StateScreen
          icon="mail"
          title="Solicite um código"
          text="O desafio expirou ou a tela foi aberta sem um pedido de código."
          actions={
            <Btn
              tone="primary"
              go={purpose === 'password_reset' ? 'forgot-password' : 'signup-email'}
            >
              Pedir código
            </Btn>
          }
        />
      </Page>
    );
  }

  const verify = async () => {
    if (!challengeId || busy) {
      return;
    }
    if (code.length !== 6) {
      setFeedback({ message: 'Digite os 6 dígitos.', unavailable: false });
      return;
    }
    setBusy(true);
    setFeedback(null);
    try {
      await api.auth.emailVerify(challengeId, code);
      setAuth({ purpose, email, verifiedChallengeId: challengeId, challengeId });
      if (purpose === 'password_reset') {
        nav.replace('reset-password', { email, challengeId });
      } else {
        nav.replace('signup-password', { email, challengeId });
      }
    } catch (error) {
      const info = emailError(error);
      setFeedback(info);
      if (error instanceof ApiError && error.code === 'invalid_code_or_challenge') {
        setCode('');
      }
    } finally {
      setBusy(false);
    }
  };

  const resend = async () => {
    if (!canResend || !challengeId) {
      return;
    }
    setResending(true);
    setFeedback(null);
    try {
      const challenge = await api.auth.emailRequestCode(email, purpose);
      setChallengeId(challenge.challenge_id);
      setExpiresAt(challenge.expires_at);
      setResendAt(Date.now() + challenge.resend_after_seconds * 1000);
      setCode('');
      setDeliveryNotice('Enviamos um novo código. A entrega pode levar alguns minutos.');
    } catch (error) {
      const info = emailError(error);
      setFeedback(info);
      if (error instanceof ApiError && error.retryAfterSeconds != null) {
        setResendAt(Date.now() + error.retryAfterSeconds * 1000);
      }
    } finally {
      setResending(false);
    }
  };

  return (
    <Page title="Digite o código">
      <Txt variant="lead">
        Código para <Text style={{ fontWeight: '800', color: palette.ink }}>{email}</Text>.
      </Txt>
      <Notice tone="blue" icon="mail">
        {deliveryNotice} Mantenha esta tela aberta.
      </Notice>
      <CodeInput
        value={code}
        onChange={setCode}
        onComplete={() => {
          if (code.length === 6) {
            void verify();
          }
        }}
      />
      <Row between>
        <Txt variant="tiny">
          {expiresRemaining == null
            ? 'Código de uso único'
            : expiresRemaining > 0
              ? `Expira em ${formatCountdown(expiresRemaining)}`
              : 'Código expirado'}
        </Txt>
        <TextBtn muted onPress={resend} disabled={!canResend}>
          {resendRemaining > 0 ? `Reenviar em ${resendRemaining}s` : 'Reenviar código'}
        </TextBtn>
      </Row>
      {feedback ? (
        <Notice tone="orange" icon="alert">
          {feedback.message}
        </Notice>
      ) : null}
      <Btn tone="primary" onPress={verify} disabled={busy || code.length !== 6}>
        {busy ? 'Verificando…' : 'Verificar'}
      </Btn>
      <TextBtn
        muted
        onPress={() =>
          nav.replace(purpose === 'password_reset' ? 'forgot-password' : 'signup-email')
        }
      >
        Trocar e-mail
      </TextBtn>
    </Page>
  );
}

function SignupPassword() {
  const nav = useNav();
  const { setSession, loadProfile, setOnboarding } = useApp();
  const email = typeof nav.params.email === 'string' ? nav.params.email : '';
  const challengeId = typeof nav.params.challengeId === 'string' ? nav.params.challengeId : null;
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<EmailErrorInfo | null>(null);
  const [pendingTokens, setPendingTokens] = useState<Tokens | null>(null);

  const finish = async (tokens: Tokens) => {
    await setSession(tokens);
    if (displayName.trim()) {
      setOnboarding({ displayName: displayName.trim() });
    }
    await loadProfile();
    nav.reset('onboarding-1');
  };

  const create = async () => {
    if (!challengeId || !email || busy) {
      return;
    }
    if (!password) {
      setFeedback({ message: 'Defina uma senha para continuar.', unavailable: false });
      return;
    }
    if (password !== confirmation) {
      setFeedback({ message: 'As senhas não conferem.', unavailable: false });
      return;
    }
    setBusy(true);
    setFeedback(null);
    try {
      const tokens = await api.auth.emailRegister(
        challengeId,
        email,
        password,
        displayName.trim() || null,
        deviceInfo(),
      );
      const keys = await api.auth.passkeys(tokens.access_token).catch(() => null);
      if (keys && keys.credentials.length === 0 && passkeyAvailable()) {
        setPendingTokens(tokens);
        return;
      }
      await finish(tokens);
    } catch (error) {
      const info = emailError(error);
      setFeedback(info);
      if (error instanceof ApiError && error.code === 'email_already_registered') {
        setFeedback({
          message: 'Este e-mail já tem conta. Entre com sua senha.',
          unavailable: false,
        });
      }
    } finally {
      setBusy(false);
    }
  };

  if (!challengeId || !email) {
    return (
      <Page title="Defina sua senha">
        <StateScreen
          icon="mail"
          title="Verificação expirada"
          text="Recomece o cadastro para confirmar o e-mail antes de definir a senha."
          actions={
            <Btn tone="primary" go="signup-email">
              Recomeçar
            </Btn>
          }
        />
      </Page>
    );
  }

  if (pendingTokens) {
    return (
      <PasskeyPrompt
        accessToken={pendingTokens.access_token}
        nextLabel="Continuar sem passkey"
        onDone={() => {
          const tokens = pendingTokens;
          setPendingTokens(null);
          void finish(tokens);
        }}
      />
    );
  }

  return (
    <Page title="Defina sua senha">
      <Txt variant="lead">
        Seu e-mail foi confirmado. Crie a senha que você usará para entrar nas próximas vezes.
      </Txt>
      <Field label="Nome de exibição (opcional)">
        <Input
          value={displayName}
          onChangeText={setDisplayName}
          maxLength={60}
          autoCapitalize="words"
          placeholder="Como os outros te veem"
        />
      </Field>
      <PasswordInput
        label="Senha"
        value={password}
        onChangeText={setPassword}
        placeholder="Sua senha"
        autoComplete="new-password"
        textContentType="newPassword"
      />
      <PasswordInput
        label="Repetir senha"
        value={confirmation}
        onChangeText={setConfirmation}
        placeholder="Repita a senha"
        autoComplete="new-password"
        textContentType="newPassword"
      />
      <PasswordHint password={password} />
      <Notice tone="blue" icon="shield">
        A senha fica só no servidor. O app guarda apenas os tokens de sessão no Keychain/Keystore.
      </Notice>
      {feedback ? (
        <Notice tone="orange" icon="alert">
          {feedback.message}
        </Notice>
      ) : null}
      <Btn tone="primary" onPress={create} disabled={busy}>
        {busy ? 'Criando conta…' : 'Criar conta'}
      </Btn>
      {feedback?.message.startsWith('Este e-mail já tem conta') ? (
        <Btn tone="ghost" go="login-email">
          Entrar com e-mail e senha
        </Btn>
      ) : (
        <TextBtn
          muted
          onPress={() => nav.replace('email-code', { email, purpose: 'registration', challengeId })}
        >
          Voltar ao código
        </TextBtn>
      )}
    </Page>
  );
}

function PasskeyPrompt({
  accessToken,
  onDone,
  nextLabel,
}: {
  accessToken: string;
  onDone: () => void;
  nextLabel: string;
}) {
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const create = async () => {
    if (busy) {
      return;
    }
    if (!passkeyAvailable()) {
      onDone();
      return;
    }
    setBusy(true);
    setFeedback(null);
    try {
      const options = await api.auth.passkeyRegistrationOptions(accessToken);
      const credential = await createPasskey(options.public_key);
      await api.auth.passkeyRegistrationVerify(
        accessToken,
        options.challenge_id,
        credential,
        Platform.OS === 'ios' ? 'iPhone' : 'Android',
      );
      onDone();
    } catch {
      setFeedback('Não foi possível criar a passkey agora. Você pode tentar depois em Segurança.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Page title="Entrar sem senha">
      <StateScreen
        icon="shield"
        title="Criar uma passkey?"
        text="Use a biometria ou o bloqueio do aparelho para entrar mais rápido nas próximas vezes. A senha continua valendo."
      />
      {!passkeyAvailable() ? (
        <Notice tone="orange" icon="info">
          Este ambiente não suporta passkey. Você pode criar depois em Segurança no development
          build.
        </Notice>
      ) : null}
      {feedback ? (
        <Notice tone="orange" icon="alert">
          {feedback}
        </Notice>
      ) : null}
      <Btn tone="primary" onPress={create} disabled={busy || !passkeyAvailable()}>
        {busy ? 'Criando…' : 'Criar passkey'}
      </Btn>
      <Btn tone="ghost" onPress={onDone} disabled={busy}>
        {nextLabel}
      </Btn>
    </Page>
  );
}

function EmailLogin() {
  const nav = useNav();
  const { auth, setAuth, setSession, loadProfile } = useApp();
  const [email, setEmail] = useState(auth.email);
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<EmailErrorInfo | null>(null);
  const [cooldownUntil, setCooldownUntil] = useState(0);
  const [pendingTokens, setPendingTokens] = useState<Tokens | null>(null);
  const now = useNow(cooldownUntil > 0);
  const cooldownRemaining = Math.max(0, Math.ceil((cooldownUntil - now) / 1000));

  const finish = async (tokens: Tokens) => {
    await setSession(tokens);
    setAuth({ email: email.trim() });
    await loadProfile();
    nav.reset('home');
  };

  const login = async () => {
    if (busy) {
      return;
    }
    if (!email.trim() || !password) {
      setFeedback({ message: 'Informe e-mail e senha.', unavailable: false });
      return;
    }
    setBusy(true);
    setFeedback(null);
    try {
      const tokens = await api.auth.emailPasswordLogin(email.trim(), password, deviceInfo());
      const keys = await api.auth.passkeys(tokens.access_token).catch(() => null);
      if (keys && keys.credentials.length === 0 && passkeyAvailable()) {
        setPendingTokens(tokens);
        return;
      }
      await finish(tokens);
    } catch (error) {
      if (error instanceof ApiError) {
        if (error.status === 401) {
          setFeedback({ message: 'E-mail ou senha inválidos.', unavailable: false });
        } else if (error.retryAfterSeconds != null) {
          setCooldownUntil(Date.now() + error.retryAfterSeconds * 1000);
          setFeedback({
            message: `Muitas tentativas. Aguarde ${error.retryAfterSeconds}s.`,
            unavailable: false,
          });
        } else {
          setFeedback(emailError(error));
        }
      } else {
        setFeedback(emailError(error));
      }
    } finally {
      setBusy(false);
    }
  };

  if (feedback?.unavailable) {
    return (
      <Page title="Entrar">
        <StateScreen
          icon="mail"
          title="E-mail indisponível nesta versão"
          text="O login por e-mail está desligado no servidor. Use a passkey para entrar ou tente mais tarde."
          actions={
            <Btn tone="primary" go="login">
              Usar passkey
            </Btn>
          }
        />
      </Page>
    );
  }

  if (pendingTokens) {
    return (
      <PasskeyPrompt
        accessToken={pendingTokens.access_token}
        nextLabel="Entrar sem passkey"
        onDone={() => {
          const tokens = pendingTokens;
          setPendingTokens(null);
          void finish(tokens);
        }}
      />
    );
  }

  return (
    <Page title="Entrar">
      <Txt variant="lead">
        Entre com o e-mail e a senha da sua conta. A passkey continua disponível na tela anterior.
      </Txt>
      <Field label="E-mail">
        <Input
          value={email}
          onChangeText={setEmail}
          keyboardType="email-address"
          autoCapitalize="none"
          autoCorrect={false}
          autoComplete="email"
          textContentType="emailAddress"
          maxLength={254}
          placeholder="voce@exemplo.com"
        />
      </Field>
      <PasswordInput
        label="Senha"
        value={password}
        onChangeText={setPassword}
        placeholder="Sua senha"
        autoComplete="current-password"
        textContentType="password"
      />
      {feedback ? (
        <Notice tone="orange" icon="alert">
          {feedback.message}
        </Notice>
      ) : null}
      <Btn
        tone="primary"
        onPress={login}
        disabled={busy || cooldownRemaining > 0 || !email.trim() || !password}
      >
        {busy ? 'Entrando…' : cooldownRemaining > 0 ? `Aguarde ${cooldownRemaining}s` : 'Entrar'}
      </Btn>
      <TextBtn muted go="forgot-password">
        Esqueci minha senha
      </TextBtn>
      <TextBtn
        muted
        onPress={() => {
          setAuth({ purpose: 'registration' });
          nav.go('signup-email');
        }}
      >
        Criar conta
      </TextBtn>
      <Row between style={{ marginTop: 4 }}>
        <Txt variant="tiny" color="soft">
          Sua senha não fica salva no aparelho.
        </Txt>
        <TextBtn muted go="login">
          Usar passkey
        </TextBtn>
      </Row>
      <View style={{ height: 1 }} />
      <TextBtn muted go="support">
        Falar com suporte
      </TextBtn>
    </Page>
  );
}

function ForgotPassword() {
  const nav = useNav();
  const { setAuth } = useApp();
  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<EmailErrorInfo | null>(null);
  const [cooldownUntil, setCooldownUntil] = useState(0);
  const now = useNow(cooldownUntil > 0);
  const cooldownRemaining = Math.max(0, Math.ceil((cooldownUntil - now) / 1000));

  const request = async () => {
    if (!email.trim() || busy) {
      return;
    }
    setBusy(true);
    setFeedback(null);
    try {
      const challenge = await api.auth.emailRequestCode(email.trim(), 'password_reset');
      setAuth({
        purpose: 'password_reset',
        email: email.trim(),
        challengeId: challenge.challenge_id,
      });
      nav.go('email-code', {
        email: email.trim(),
        purpose: 'password_reset',
        challengeId: challenge.challenge_id,
        expiresAt: challenge.expires_at,
        resendAfter: challenge.resend_after_seconds,
      });
    } catch (error) {
      setFeedback(emailError(error));
      if (error instanceof ApiError && error.retryAfterSeconds != null) {
        setCooldownUntil(Date.now() + error.retryAfterSeconds * 1000);
      }
    } finally {
      setBusy(false);
    }
  };

  if (feedback?.unavailable) {
    return (
      <Page title="Esqueci minha senha">
        <StateScreen
          icon="mail"
          title="E-mail indisponível nesta versão"
          text="A recuperação por e-mail está desligada no servidor. Use a passkey ou fale com o suporte."
          actions={
            <Btn tone="primary" go="login">
              Voltar para entrar
            </Btn>
          }
        />
      </Page>
    );
  }

  return (
    <Page title="Esqueci minha senha">
      <Txt variant="lead">
        Informe o e-mail da conta. Se ele existir, enviaremos um código para redefinir a senha.
      </Txt>
      <Field label="E-mail">
        <Input
          value={email}
          onChangeText={setEmail}
          keyboardType="email-address"
          autoCapitalize="none"
          autoCorrect={false}
          autoComplete="email"
          textContentType="emailAddress"
          maxLength={254}
          placeholder="voce@exemplo.com"
        />
      </Field>
      <Notice tone="blue" icon="mail">
        A entrega é assíncrona e pode levar alguns minutos. Não feche a próxima tela.
      </Notice>
      {feedback ? (
        <Notice tone="orange" icon="alert">
          {feedback.message}
        </Notice>
      ) : null}
      <Btn
        tone="primary"
        onPress={request}
        disabled={busy || cooldownRemaining > 0 || !email.trim()}
      >
        {busy
          ? 'Solicitando…'
          : cooldownRemaining > 0
            ? `Aguarde ${cooldownRemaining}s`
            : 'Enviar código'}
      </Btn>
      <Btn tone="ghost" go="login-email">
        Voltar para entrar
      </Btn>
    </Page>
  );
}

function ResetPassword() {
  const nav = useNav();
  const { session, signOut } = useApp();
  const email = typeof nav.params.email === 'string' ? nav.params.email : '';
  const challengeId = typeof nav.params.challengeId === 'string' ? nav.params.challengeId : null;
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<EmailErrorInfo | null>(null);
  const [cooldownUntil, setCooldownUntil] = useState(0);
  const now = useNow(cooldownUntil > 0);
  const cooldownRemaining = Math.max(0, Math.ceil((cooldownUntil - now) / 1000));

  const reset = async () => {
    if (!challengeId || !email || busy) {
      return;
    }
    if (!password) {
      setFeedback({ message: 'Defina a nova senha.', unavailable: false });
      return;
    }
    if (password !== confirmation) {
      setFeedback({ message: 'As senhas não conferem.', unavailable: false });
      return;
    }
    setBusy(true);
    setFeedback(null);
    try {
      await api.auth.passwordReset(challengeId, email, password);
      if (session) {
        await signOut();
      }
      nav.reset('login-email');
      nav.toast('Senha redefinida. Entre com a nova senha.');
    } catch (error) {
      setFeedback(emailError(error));
      if (error instanceof ApiError && error.retryAfterSeconds != null) {
        setCooldownUntil(Date.now() + error.retryAfterSeconds * 1000);
        setFeedback({
          message: `Muitas tentativas. Aguarde ${error.retryAfterSeconds}s.`,
          unavailable: false,
        });
      }
    } finally {
      setBusy(false);
    }
  };

  if (!challengeId || !email) {
    return (
      <Page title="Nova senha">
        <StateScreen
          icon="mail"
          title="Verificação expirada"
          text="Solicite um novo código para redefinir a senha."
          actions={
            <Btn tone="primary" go="forgot-password">
              Solicitar código
            </Btn>
          }
        />
      </Page>
    );
  }

  return (
    <Page title="Nova senha">
      <Txt variant="lead">
        Crie a nova senha para <Text style={{ fontWeight: '800' }}>{email}</Text>.
      </Txt>
      <PasswordInput
        label="Nova senha"
        value={password}
        onChangeText={setPassword}
        placeholder="Nova senha"
        autoComplete="new-password"
        textContentType="newPassword"
      />
      <PasswordInput
        label="Repetir nova senha"
        value={confirmation}
        onChangeText={setConfirmation}
        placeholder="Repita a nova senha"
        autoComplete="new-password"
        textContentType="newPassword"
      />
      <PasswordHint password={password} />
      <Notice tone="orange" icon="shield">
        Ao redefinir a senha, as outras sessões serão encerradas. Você precisará entrar de novo.
      </Notice>
      {feedback ? (
        <Notice tone="orange" icon="alert">
          {feedback.message}
        </Notice>
      ) : null}
      <Btn tone="primary" onPress={reset} disabled={busy || cooldownRemaining > 0}>
        {busy
          ? 'Salvando…'
          : cooldownRemaining > 0
            ? `Aguarde ${cooldownRemaining}s`
            : 'Redefinir senha'}
      </Btn>
      <Btn tone="ghost" go="forgot-password">
        Pedir outro código
      </Btn>
    </Page>
  );
}

function ChangePassword() {
  const nav = useNav();
  const { session, signOut } = useApp();
  const [currentPassword, setCurrentPassword] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<EmailErrorInfo | null>(null);
  const [cooldownUntil, setCooldownUntil] = useState(0);
  const now = useNow(cooldownUntil > 0);
  const cooldownRemaining = Math.max(0, Math.ceil((cooldownUntil - now) / 1000));

  const change = async () => {
    if (!session || busy) {
      return;
    }
    if (!currentPassword || !password) {
      setFeedback({ message: 'Informe a senha atual e a nova senha.', unavailable: false });
      return;
    }
    if (password !== confirmation) {
      setFeedback({ message: 'As senhas não conferem.', unavailable: false });
      return;
    }
    setBusy(true);
    setFeedback(null);
    try {
      await api.auth.changePassword(session.accessToken, currentPassword, password);
      nav.back();
      nav.toast('Senha alterada.');
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        await signOut();
        nav.reset('login-email');
        nav.toast('Sessão encerrada. Entre novamente com a nova senha.');
      } else {
        setFeedback(emailError(error));
        if (error instanceof ApiError && error.retryAfterSeconds != null) {
          setCooldownUntil(Date.now() + error.retryAfterSeconds * 1000);
          setFeedback({
            message: `Muitas tentativas. Aguarde ${error.retryAfterSeconds}s.`,
            unavailable: false,
          });
        }
      }
    } finally {
      setBusy(false);
    }
  };

  if (!session) {
    return <EmailLogin />;
  }

  return (
    <Page title="Trocar senha">
      <PasswordInput
        label="Senha atual"
        value={currentPassword}
        onChangeText={setCurrentPassword}
        placeholder="Senha atual"
        autoComplete="current-password"
        textContentType="password"
      />
      <PasswordInput
        label="Nova senha"
        value={password}
        onChangeText={setPassword}
        placeholder="Nova senha"
        autoComplete="new-password"
        textContentType="newPassword"
      />
      <PasswordInput
        label="Repetir nova senha"
        value={confirmation}
        onChangeText={setConfirmation}
        placeholder="Repita a nova senha"
        autoComplete="new-password"
        textContentType="newPassword"
      />
      <PasswordHint password={password} />
      <Notice tone="orange" icon="shield">
        Ao trocar a senha, as outras sessões serão encerradas. Esta continua válida.
      </Notice>
      {feedback ? (
        <Notice tone="orange" icon="alert">
          {feedback.message}
        </Notice>
      ) : null}
      <Btn tone="primary" onPress={change} disabled={busy || cooldownRemaining > 0}>
        {busy
          ? 'Salvando…'
          : cooldownRemaining > 0
            ? `Aguarde ${cooldownRemaining}s`
            : 'Salvar nova senha'}
      </Btn>
      <Btn tone="ghost" back>
        Cancelar
      </Btn>
    </Page>
  );
}

function Credentials() {
  const { palette } = useTheme();
  const { session } = useApp();
  const [emails, setEmails] = useState<EmailCredential[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState<string | null>(null);

  const load = () => {
    if (!session) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setFailed(null);
    api.auth
      .emails(session.accessToken)
      .then((result) => setEmails(result.emails))
      .catch((error) => setFailed(emailError(error).message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session]);

  if (!session) {
    return (
      <Page title="Credenciais">
        <EmptyState
          title="Entre na conta"
          text="As credenciais de login aparecem quando você está autenticado."
          actions={
            <Btn tone="primary" go="login">
              Entrar
            </Btn>
          }
        />
      </Page>
    );
  }

  if (loading) {
    return (
      <Page title="Credenciais">
        <LoadingState label="Buscando suas credenciais." variant="cards" />
      </Page>
    );
  }

  return (
    <Page title="Credenciais">
      <Card>
        <Row between>
          <Txt variant="h3">E-mail de login</Txt>
          <Badge tone="green">CREDENCIAL</Badge>
        </Row>
        <Txt variant="tiny" style={{ marginTop: 6 }}>
          Este é o endereço que autentica sua conta. Ele é diferente do e-mail do pagador usado no
          Pix.
        </Txt>
      </Card>
      {failed ? (
        <Notice tone="orange" icon="alert">
          {failed}
        </Notice>
      ) : null}
      <CardList>
        {emails.map((item, index) => (
          <ListRow key={item.email} last={index === emails.length - 1}>
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                {item.email}
              </Text>
              <Text style={{ fontSize: 13, color: palette.muted, marginTop: 2 }}>
                {item.verified_at ? 'Verificado' : 'Não verificado'}
                {item.is_primary ? ' · principal' : ''}
              </Text>
            </View>
            {item.is_primary ? <Badge tone="lime">PRINCIPAL</Badge> : null}
          </ListRow>
        ))}
      </CardList>
      {emails.length === 0 && !failed ? (
        <Notice tone="blue" icon="info">
          Nenhuma credencial de e-mail listada. Se você entra por passkey, o e-mail pode ser
          adicionado depois.
        </Notice>
      ) : null}
      <Btn tone="primary" go="email-change">
        Trocar e-mail de login
      </Btn>
      <Notice tone="orange" icon="clock">
        Uma troca de e-mail só pode ser feita a cada 24 h. As outras sessões são encerradas; esta
        continua válida.
      </Notice>
      <Btn tone="ghost" go="change-password">
        Trocar senha
      </Btn>
      <Btn tone="ghost" onPress={() => load()}>
        Atualizar
      </Btn>
    </Page>
  );
}

function EmailChange() {
  const nav = useNav();
  const { session } = useApp();
  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<EmailErrorInfo | null>(null);

  const request = async () => {
    if (!session || busy) {
      return;
    }
    const normalized = email.trim();
    if (!normalized) {
      setFeedback({ message: 'Informe o novo e-mail.', unavailable: false });
      return;
    }
    setBusy(true);
    setFeedback(null);
    try {
      const challenge = await api.auth.emailChangeChallenge(session.accessToken, normalized);
      nav.go('email-change-code', {
        newEmail: normalized,
        challengeId: challenge.challenge_id,
        expiresAt: challenge.expires_at,
        resendAfter: challenge.resend_after_seconds,
      });
    } catch (error) {
      const info = emailError(error);
      if (error instanceof ApiError && error.retryAfterSeconds != null) {
        const hours = Math.ceil(error.retryAfterSeconds / 3600);
        setFeedback({
          message: `Nova troca disponível em aproximadamente ${hours} h.`,
          unavailable: false,
        });
      } else {
        setFeedback(info);
      }
    } finally {
      setBusy(false);
    }
  };

  if (!session) {
    return (
      <Page title="Trocar e-mail">
        <StateScreen
          icon="lock"
          title="Entre na conta"
          text="A troca de credencial exige uma sessão autenticada."
          actions={
            <Btn tone="primary" go="login">
              Entrar
            </Btn>
          }
        />
      </Page>
    );
  }

  return (
    <Page title="Trocar e-mail">
      <Txt variant="lead">
        O código vai para o endereço novo. A entrega pode levar alguns minutos.
      </Txt>{' '}
      <Field label="Novo e-mail">
        <Input
          value={email}
          onChangeText={setEmail}
          keyboardType="email-address"
          autoCapitalize="none"
          autoCorrect={false}
          textContentType="emailAddress"
          maxLength={254}
          placeholder="novo@exemplo.com"
        />
      </Field>
      {feedback ? (
        <Notice tone="orange" icon="alert">
          {feedback.message}
        </Notice>
      ) : null}
      <Notice tone="orange" icon="shield">
        Ao confirmar, o endereço antigo deixa de autenticar. As outras sessões são encerradas; esta
        continua válida.
      </Notice>
      <Btn tone="primary" onPress={request} disabled={busy || !email.trim()}>
        {busy ? 'Solicitando…' : 'Enviar código ao novo e-mail'}
      </Btn>
      <Btn tone="ghost" go="credentials">
        Cancelar
      </Btn>
    </Page>
  );
}

function EmailChangeCode() {
  const nav = useNav();
  const { palette } = useTheme();
  const { session } = useApp();
  const newEmail = typeof nav.params.newEmail === 'string' ? nav.params.newEmail : '';
  const initialChallenge =
    typeof nav.params.challengeId === 'string' ? nav.params.challengeId : null;
  const initialExpires = typeof nav.params.expiresAt === 'string' ? nav.params.expiresAt : null;
  const initialResend = typeof nav.params.resendAfter === 'number' ? nav.params.resendAfter : 60;
  const [challengeId, setChallengeId] = useState(initialChallenge);
  const [expiresAt, setExpiresAt] = useState(initialExpires);
  const [resendAt, setResendAt] = useState(() => Date.now() + initialResend * 1000);
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [resending, setResending] = useState(false);
  const [feedback, setFeedback] = useState<EmailErrorInfo | null>(null);
  const [deliveryNotice, setDeliveryNotice] = useState('Enviamos o código ao novo endereço.');
  const now = useNow(true);
  const resendRemaining = Math.max(0, Math.ceil((resendAt - now) / 1000));
  const expiresRemaining = secondsUntil(expiresAt);
  const canResend = !resending && resendRemaining === 0;

  const confirm = async () => {
    if (!session || !challengeId || busy) {
      return;
    }
    if (code.length !== 6) {
      setFeedback({ message: 'Digite os 6 dígitos.', unavailable: false });
      return;
    }
    setBusy(true);
    setFeedback(null);
    try {
      await api.auth.emailChangeConfirm(session.accessToken, newEmail, challengeId, code);
      nav.reset('credentials');
      nav.toast('E-mail alterado. As outras sessões foram encerradas.');
    } catch (error) {
      const info = emailError(error);
      setFeedback(info);
      if (error instanceof ApiError && error.code === 'invalid_email_change') {
        setCode('');
      }
      if (error instanceof ApiError && error.retryAfterSeconds != null) {
        const hours = Math.ceil(error.retryAfterSeconds / 3600);
        setFeedback({
          message: `Troca recente. Nova tentativa em aproximadamente ${hours} h.`,
          unavailable: false,
        });
      }
    } finally {
      setBusy(false);
    }
  };

  const resend = async () => {
    if (!session || !canResend) {
      return;
    }
    setResending(true);
    setFeedback(null);
    try {
      const challenge = await api.auth.emailChangeChallenge(session.accessToken, newEmail);
      setChallengeId(challenge.challenge_id);
      setExpiresAt(challenge.expires_at);
      setResendAt(Date.now() + challenge.resend_after_seconds * 1000);
      setCode('');
      setDeliveryNotice('Enviamos outro código ao novo endereço.');
    } catch (error) {
      const info = emailError(error);
      setFeedback(info);
      if (error instanceof ApiError && error.retryAfterSeconds != null) {
        setResendAt(Date.now() + error.retryAfterSeconds * 1000);
      }
    } finally {
      setResending(false);
    }
  };

  if (!session || !challengeId) {
    return (
      <Page title="Confirme o novo e-mail">
        <StateScreen
          icon="lock"
          title="Troca indisponível"
          text="Solicite um novo código para o endereço novo antes de confirmar."
          actions={
            <Btn tone="primary" go="email-change">
              Solicitar código
            </Btn>
          }
        />
      </Page>
    );
  }

  return (
    <Page title="Confirme o novo e-mail">
      <Txt variant="lead">
        Código para <Text style={{ fontWeight: '800', color: palette.ink }}>{newEmail}</Text>.
      </Txt>
      <Notice tone="blue" icon="mail">
        {deliveryNotice} A entrega pode levar alguns minutos; mantenha esta tela aberta.
      </Notice>
      <CodeInput
        value={code}
        onChange={setCode}
        onComplete={() => {
          if (code.length === 6) {
            void confirm();
          }
        }}
      />
      <Row between>
        <Txt variant="tiny">
          {expiresRemaining == null
            ? 'Código de uso único'
            : expiresRemaining > 0
              ? `Expira em ${formatCountdown(expiresRemaining)}`
              : 'Código expirado'}
        </Txt>
        <TextBtn muted onPress={resend} disabled={!canResend}>
          {resendRemaining > 0 ? `Reenviar em ${resendRemaining}s` : 'Reenviar código'}
        </TextBtn>
      </Row>
      {feedback ? (
        <Notice tone="orange" icon="alert">
          {feedback.message}
        </Notice>
      ) : null}
      <Btn tone="primary" onPress={confirm} disabled={busy || code.length !== 6}>
        {busy ? 'Confirmando…' : 'Confirmar troca'}
      </Btn>
      <Btn tone="ghost" go="credentials">
        Cancelar
      </Btn>
    </Page>
  );
}

export const emailScreens: ScreenDef[] = [
  { id: 'signup-email', render: () => <EmailEntry /> },
  { id: 'login-email', render: () => <EmailLogin /> },
  { id: 'email-code', render: () => <EmailCode /> },
  { id: 'signup-password', render: () => <SignupPassword /> },
  { id: 'forgot-password', render: () => <ForgotPassword /> },
  { id: 'reset-password', render: () => <ResetPassword /> },
  { id: 'change-password', tab: 'perfil', render: () => <ChangePassword /> },
  { id: 'credentials', tab: 'perfil', render: () => <Credentials /> },
  { id: 'email-change', tab: 'perfil', render: () => <EmailChange /> },
  { id: 'email-change-code', tab: 'perfil', render: () => <EmailChangeCode /> },
];
