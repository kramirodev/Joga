import { useEffect, useRef, useState, type ElementRef } from 'react';
import { Platform, TextInput, View } from 'react-native';

import { api, ApiError } from '../api/client';
import type { EmailCredential } from '../api/types';
import { authConfig } from '../auth/config';
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

type EmailPurpose = 'registration' | 'login';

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
    invalid_email: 'Informe um e-mail válido.',
    email_domain_not_allowed: 'Este domínio de e-mail não é aceito.',
    invalid_code_or_challenge: 'Código inválido ou expirado.',
    invalid_receipt: 'A verificação expirou. Recomece o fluxo.',
    invalid_email_login:
      'Esta credencial não serve para entrar. Confira o endereço ou use outro método.',
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

function EmailEntry({ purpose }: { purpose: EmailPurpose }) {
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
  const registration = purpose === 'registration';

  const request = async () => {
    const normalized = email.trim();
    if (!normalized) {
      setFeedback({ message: 'Informe seu e-mail.', unavailable: false });
      return;
    }
    if (registration && !accepted) {
      setFeedback({ message: 'Aceite os termos para continuar.', unavailable: false });
      return;
    }
    setBusy(true);
    setFeedback(null);
    try {
      const challenge = await api.auth.emailRequestCode(normalized, purpose);
      setAuth({ purpose, email: normalized, challengeId: challenge.challenge_id });
      nav.go('email-code', {
        email: normalized,
        purpose,
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
      <Page title={registration ? 'Criar conta' : 'Entrar'}>
        <StateScreen
          icon="mail"
          title="E-mail indisponível nesta versão"
          text="O método por e-mail está desligado no servidor. Use a passkey para entrar ou tente novamente quando o método estiver disponível."
          actions={
            <>
              <Btn tone="primary" go="login">
                Usar passkey
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
    <Page title={registration ? 'Criar conta' : 'Entrar'}>
      <Txt variant="lead">
        {registration
          ? 'Vamos confirmar seu e-mail com um código de 6 dígitos. Depois você escolhe o nome de exibição.'
          : 'Informe o e-mail da sua conta. Vamos enviar um código de 6 dígitos.'}
      </Txt>
      <Field label="E-mail">
        <Input
          value={email}
          onChangeText={setEmail}
          keyboardType="email-address"
          autoCapitalize="none"
          autoCorrect={false}
          textContentType="emailAddress"
          maxLength={254}
          placeholder="voce@exemplo.com"
        />
      </Field>
      {registration ? (
        <Check checked={accepted} onChange={setAccepted}>
          Aceito os <Text style={{ fontWeight: '800', color: palette.ink }}>Termos de uso</Text> e a{' '}
          <Text style={{ fontWeight: '800', color: palette.ink }}>Política de privacidade</Text>.
        </Check>
      ) : null}
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
          setAuth({ purpose: registration ? 'login' : 'registration' });
          nav.replace(registration ? 'login-email' : 'signup-email');
        }}
      >
        {registration ? 'Já tenho conta' : 'Criar conta com e-mail'}
      </TextBtn>
      {authConfig.phoneEnabled ? (
        <TextBtn
          muted
          onPress={() => {
            setAuth({ purpose });
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
  const { setAuth, setSession, loadProfile } = useApp();
  const email = typeof nav.params.email === 'string' ? nav.params.email : '';
  const purpose: EmailPurpose = nav.params.purpose === 'login' ? 'login' : 'registration';
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
            <Btn tone="primary" go={purpose === 'login' ? 'login-email' : 'signup-email'}>
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
      if (purpose === 'login') {
        const tokens = await api.auth.emailLogin(challengeId, email, deviceInfo());
        await setSession(tokens);
        await loadProfile();
        nav.reset('home');
      } else {
        setAuth({ purpose, email, verifiedChallengeId: challengeId, challengeId });
        nav.replace('email-name', { email, challengeId });
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
        onPress={() => nav.replace(purpose === 'registration' ? 'signup-email' : 'login-email')}
      >
        Trocar e-mail
      </TextBtn>
    </Page>
  );
}

function EmailName() {
  const nav = useNav();
  const { setAuth, setSession, loadProfile, setOnboarding } = useApp();
  const email = typeof nav.params.email === 'string' ? nav.params.email : '';
  const challengeId = typeof nav.params.challengeId === 'string' ? nav.params.challengeId : null;
  const [displayName, setDisplayName] = useState('');
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<EmailErrorInfo | null>(null);
  const [alreadyRegistered, setAlreadyRegistered] = useState(false);

  const create = async () => {
    if (!challengeId || !email || busy) {
      return;
    }
    setBusy(true);
    setFeedback(null);
    try {
      const tokens = await api.auth.emailRegister(
        challengeId,
        email,
        displayName.trim() || null,
        deviceInfo(),
      );
      await setSession(tokens);
      if (displayName.trim()) {
        setOnboarding({ displayName: displayName.trim() });
      }
      await loadProfile();
      nav.reset('onboarding-1');
    } catch (error) {
      const info = emailError(error);
      setFeedback(info);
      if (error instanceof ApiError && error.code === 'email_already_registered') {
        setAlreadyRegistered(true);
      }
    } finally {
      setBusy(false);
    }
  };

  if (!challengeId || !email) {
    return (
      <Page title="Como você aparece?">
        <StateScreen
          icon="mail"
          title="Verificação expirada"
          text="Recomece o cadastro para confirmar o e-mail antes de escolher o nome."
          actions={
            <Btn tone="primary" go="signup-email">
              Recomeçar
            </Btn>
          }
        />
      </Page>
    );
  }

  return (
    <Page title="Como você aparece?">
      <Txt variant="lead">
        Seu e-mail já foi confirmado. Escolha um nome de exibição ou deixe em branco para decidir
        depois.
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
      <Notice tone="blue" icon="shield">
        Seu e-mail de login não aparece no perfil público.
      </Notice>
      {feedback ? (
        <Notice tone="orange" icon="alert">
          {feedback.message}
        </Notice>
      ) : null}
      {alreadyRegistered ? (
        <Btn
          tone="primary"
          onPress={() => {
            setAuth({ purpose: 'login', email });
            nav.replace('login-email');
          }}
        >
          Entrar com este e-mail
        </Btn>
      ) : (
        <Btn tone="primary" onPress={create} disabled={busy || !challengeId}>
          {busy ? 'Criando conta…' : 'Criar conta'}
        </Btn>
      )}
      {!alreadyRegistered ? (
        <TextBtn
          muted
          onPress={() =>
            nav.replace('email-code', {
              email,
              purpose: 'registration',
              challengeId,
            })
          }
        >
          Voltar ao código
        </TextBtn>
      ) : null}
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
        Uma troca só pode ser feita a cada 24 h. As outras sessões são encerradas; esta continua
        válida.
      </Notice>
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
  { id: 'signup-email', render: () => <EmailEntry purpose="registration" /> },
  { id: 'login-email', render: () => <EmailEntry purpose="login" /> },
  { id: 'email-code', render: () => <EmailCode /> },
  { id: 'email-name', render: () => <EmailName /> },
  { id: 'credentials', tab: 'perfil', render: () => <Credentials /> },
  { id: 'email-change', tab: 'perfil', render: () => <EmailChange /> },
  { id: 'email-change-code', tab: 'perfil', render: () => <EmailChangeCode /> },
];
