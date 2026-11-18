import { useEffect, useMemo, useRef, useState, type ElementRef } from 'react';
import { Platform, ScrollView, TextInput, View } from 'react-native';
import * as Location from 'expo-location';

import { api, ApiError } from '../api/client';
import type { TermsVersion } from '../api/types';
import { authConfig } from '../auth/config';
import { createPasskey, getPasskey, passkeyAvailable } from '../passkey';
import { useApp } from '../state/app';
import { useNav, useTheme } from '../state/context';
import { AddWindowSheet } from '../ui/AddWindowSheet';
import { Avatar } from '../ui/Avatar';
import {
  Badge,
  Btn,
  Card,
  CardList,
  Check,
  Chip,
  ChipRow,
  Field,
  IconBtn,
  Input,
  InputPrefix,
  ListRow,
  Notice,
  Page,
  Pill,
  Progress,
  Row,
  Seg,
  SegBtn,
  StateScreen,
  TextBtn,
  Txt,
  WelcomeCourt,
} from '../ui/kit';
import { courtFromLabel, levelFromLabel } from '../ui/datetime';
import { Text } from '../ui/text';
import type { ScreenDef } from './types';

function errorText(error: unknown): string {
  if (error instanceof ApiError) {
    const messages: Record<string, string> = {
      network_unavailable: 'Não foi possível falar com o servidor.',
      invalid_phone: 'Telefone inválido.',
      rate_limited: 'Muitas tentativas. Aguarde um pouco.',
      invalid_code_or_challenge: 'Código inválido ou expirado.',
      invalid_receipt: 'Verificação expirada. Recomece o cadastro.',
      phone_already_registered: 'Este telefone já tem conta.',
      account_not_found: 'Conta não encontrada.',
      invalid_email: 'Informe um e-mail válido.',
      invalid_email_login: 'Esta credencial não serve para entrar.',
      invalid_email_change: 'Código inválido ou expirado.',
      email_already_registered: 'Este e-mail já está vinculado a uma conta.',
      email_domain_not_allowed: 'Este domínio de e-mail não é aceito.',
      email_unchanged: 'O novo e-mail é igual ao atual.',
      signup_closed: 'O cadastro está fechado neste beta.',
      email_registration_disabled: 'O cadastro por e-mail está indisponível nesta versão.',
      phone_registration_disabled: 'O cadastro por telefone está indisponível nesta versão.',
      phone_required: 'Esta ação exige telefone verificado no lançamento.',
      email_auth_disabled: 'O login por e-mail está indisponível nesta versão.',
      phone_auth_disabled: 'O login por telefone está indisponível nesta versão.',
      invalid_passkey: 'Não foi possível validar a passkey. Tente novamente.',
      passkey_already_registered: 'Esta passkey já está cadastrada.',
    };
    return messages[error.code] ?? 'Não foi possível concluir a ação.';
  }
  return 'Não foi possível concluir a ação.';
}

function phoneE164(input: string): string {
  const digits = input.replace(/\D/g, '');
  if (digits.startsWith('55') && digits.length >= 12) {
    return `+${digits}`;
  }
  return `+55${digits}`;
}

function maskPhone(input: string): string {
  const digits = input.replace(/\D/g, '').slice(-11);
  if (digits.length < 11) {
    return '+55 (11) 9****-1234';
  }
  return `+55 (${digits.slice(0, 2)}) ${digits[2]}****-${digits.slice(7)}`;
}

function PhoneMethodUnavailable() {
  return (
    <Page title="Telefone indisponível">
      <StateScreen
        icon="lock"
        title="Telefone indisponível nesta versão"
        text="O beta usa e-mail para entrar. O caminho por telefone continua preservado para o lançamento e voltará quando a credencial for habilitada."
        actions={
          <>
            <Btn tone="primary" go="login">
              Voltar para entrar
            </Btn>
            <Btn tone="ghost" go="welcome">
              Início
            </Btn>
          </>
        }
      />
    </Page>
  );
}

function Welcome() {
  const nav = useNav();
  const { setAuth } = useApp();
  const { palette } = useTheme();
  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: palette.bg }}
      contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 18, gap: 10, flexGrow: 1 }}
      showsVerticalScrollIndicator={false}
    >
      <View style={{ height: 10 }} />
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text
          style={{
            fontSize: 28,
            lineHeight: 26,
            fontWeight: '900',
            letterSpacing: -1.7,
            textTransform: 'uppercase',
            color: palette.ink,
          }}
        >
          JOGA <Text style={{ color: palette.lime }}>Y</Text> JOGA
        </Text>
        <Badge>ANDROID · iOS</Badge>
      </View>
      <View
        style={{
          backgroundColor: '#15171A',
          borderWidth: 1.5,
          borderColor: palette.line,
          borderRadius: 20,
          overflow: 'hidden',
        }}
      >
        <WelcomeCourt />
        <View
          style={{
            paddingHorizontal: 14,
            paddingVertical: 8,
            borderTopWidth: 1,
            borderTopColor: palette.lineOnInk,
          }}
        >
          <Text
            style={{
              fontSize: 11,
              lineHeight: 15,
              fontWeight: '800',
              letterSpacing: 1.4,
              textTransform: 'uppercase',
              color: palette.softOnInk,
            }}
          >
            Hoje · 20:00 · Futebol 5x5
          </Text>
        </View>
      </View>
      <View style={{ paddingTop: 2 }}>
        <Txt variant="label">Futebol e vôlei, quadra de verdade</Txt>
        <Txt variant="h1xl" style={{ marginTop: 6, marginBottom: 6 }}>
          Encontre sua{'\n'}próxima partida.
        </Txt>
        <Txt variant="lead">Jogue com pessoas do seu nível, no seu tempo e perto de você.</Txt>
      </View>
      <View style={{ gap: 9 }}>
        {[
          'Partidas casuais e ranqueadas com times equilibrados.',
          'Horário, região e tipo de quadra que combinam com você.',
          'Histórico, amigos e sua divisão sempre à mão.',
        ].map((item) => (
          <View key={item} style={{ flexDirection: 'row', gap: 10, alignItems: 'flex-start' }}>
            <View
              style={{
                width: 24,
                height: 24,
                borderRadius: 12,
                marginTop: -1,
                backgroundColor: palette.lime,
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Text style={{ color: '#F1F3F0', fontSize: 15, fontWeight: '900', lineHeight: 18 }}>
                ✓
              </Text>
            </View>
            <Txt variant="tiny" style={{ flex: 1 }}>
              {item}
            </Txt>
          </View>
        ))}
      </View>
      <View style={{ gap: 9, marginTop: 2 }}>
        <Btn
          tone="primary"
          icon="arrow"
          onPress={() => {
            setAuth({ purpose: 'registration' });
            nav.go(authConfig.signupMethod === 'phone' ? 'signup-phone' : 'signup-email');
          }}
        >
          Criar conta
        </Btn>
        <Btn
          tone="ghost"
          onPress={() => {
            setAuth({ purpose: 'login' });
            nav.go('login');
          }}
        >
          Já tenho conta
        </Btn>
        {authConfig.signupMethod === 'phone' && authConfig.emailEnabled ? (
          <TextBtn
            muted
            onPress={() => {
              setAuth({ purpose: 'registration' });
              nav.go('signup-email');
            }}
          >
            Criar conta com e-mail
          </TextBtn>
        ) : null}
      </View>
      <TextBtn muted go="login">
        Entrar com passkey
      </TextBtn>
    </ScrollView>
  );
}

function OnboardingOne() {
  const { setOnboarding } = useApp();
  const [selected, setSelected] = useState<string[]>(['Futebol 5x5']);
  const [level, setLevel] = useState('Intermediário');
  const [court, setCourt] = useState('Tanto faz');
  const { palette } = useTheme();
  const nav = useNav();
  const options = ['Futebol 5x5', 'Vôlei 6x6', 'Basquete 3x3', 'Tênis'];
  const toggle = (item: string) => {
    setSelected((current) =>
      current.includes(item) ? current.filter((value) => value !== item) : [...current, item],
    );
  };
  return (
    <Page title="O que você joga?" back={false}>
      <Row between>
        <Txt variant="label">1 de 3 · esporte</Txt>
        <Badge>2 min</Badge>
      </Row>
      <Progress value={33} />
      <ChipRow>
        {options.map((item) => (
          <Chip
            key={item}
            on={selected.includes(item)}
            icon={item === 'Futebol 5x5' ? 'bolt' : undefined}
            onPress={() => toggle(item)}
          >
            {item}
          </Chip>
        ))}
      </ChipRow>
      <Card>
        <Txt variant="h3">Seu nível no futebol 5x5</Txt>
        <Txt variant="tiny" style={{ marginTop: 4, marginBottom: 10 }}>
          Nível autodeclarado para partidas casuais.
        </Txt>
        <Seg>
          {['Iniciante', 'Intermediário', 'Avançado'].map((item) => (
            <SegBtn key={item} on={level === item} onPress={() => setLevel(item)}>
              {item}
            </SegBtn>
          ))}
        </Seg>
      </Card>
      <Card>
        <Txt variant="h3">Onde prefere jogar?</Txt>
        <Txt variant="tiny" style={{ marginTop: 4, marginBottom: 10 }}>
          É um filtro de compatibilidade, não uma fila separada.
        </Txt>
        <Seg>
          {['Públicas', 'Particulares', 'Tanto faz'].map((item) => (
            <SegBtn key={item} on={court === item} onPress={() => setCourt(item)}>
              {item}
            </SegBtn>
          ))}
        </Seg>
      </Card>
      <Notice tone="blue" icon="info">
        Você pode mudar tudo depois em{' '}
        <Text style={{ fontWeight: '800', color: palette.ink }}>
          Perfil → Modalidades e formatos
        </Text>
        .
      </Notice>
      <Btn
        tone="primary"
        onPress={() => {
          setOnboarding({
            formats: selected,
            level: levelFromLabel(level),
            courtPreference: courtFromLabel(court),
          });
          nav.go('onboarding-2');
        }}
      >
        Continuar
      </Btn>
    </Page>
  );
}

function OnboardingTwo() {
  const { onboarding, setOnboarding } = useApp();
  const { palette } = useTheme();
  const rows: { day: string; weekday: number; label: string }[] = [
    { day: 'Terça', weekday: 2, label: 'onb-0' },
    { day: 'Quarta', weekday: 3, label: 'onb-1' },
    { day: 'Sábado', weekday: 6, label: 'onb-2' },
  ];
  const windowsFor = (weekday: number) =>
    onboarding.windows.filter((window) => window.weekday === weekday);
  const [editorDay, setEditorDay] = useState<number | null>(null);
  return (
    <>
      <Page title="Quando você joga?">
        <Row between>
          <Txt variant="label">2 de 3 · disponibilidade</Txt>
          <Badge>semanal</Badge>
        </Row>
        <Progress value={66} />
        <Card>
          <Txt variant="h3">Seus horários</Txt>
          <Txt variant="tiny" style={{ marginTop: 4, marginBottom: 8 }}>
            Você pode adicionar mais de um horário no mesmo dia.
          </Txt>
          <View>
            {rows.map((row, index) => {
              const windows = windowsFor(row.weekday);
              return (
                <View
                  key={row.label}
                  style={{
                    flexDirection: 'row',
                    alignItems: 'center',
                    gap: 12,
                    paddingVertical: 11,
                    borderBottomWidth: index === rows.length - 1 ? 0 : 1,
                    borderBottomColor: palette.line,
                  }}
                >
                  <View style={{ flex: 1 }}>
                    <Text
                      style={{
                        fontSize: 14,
                        lineHeight: 17,
                        fontWeight: '800',
                        color: palette.ink,
                      }}
                    >
                      {row.day}
                    </Text>
                    <Text
                      style={{ fontSize: 13, lineHeight: 18, color: palette.muted, marginTop: 2 }}
                    >
                      {windows.length === 0
                        ? '—'
                        : windows
                            .map(
                              (window) =>
                                `${window.start_time.slice(0, 5)}–${window.end_time.slice(0, 5)}`,
                            )
                            .join('\n')}
                    </Text>
                  </View>
                  <IconBtn
                    icon="plus"
                    label={`Adicionar horário de ${row.day.toLowerCase()}`}
                    onPress={() => setEditorDay(row.weekday)}
                  />
                </View>
              );
            })}
          </View>
        </Card>
        <Card tone="flat">
          <Row between>
            <Txt variant="h3">Fuso</Txt>
            <Pill icon="globe">America/Sao_Paulo</Pill>
          </Row>
        </Card>
        <Btn tone="primary" go="onboarding-3">
          Continuar
        </Btn>
      </Page>
      <AddWindowSheet
        key={editorDay ?? 'closed'}
        visible={editorDay !== null}
        initialWeekday={editorDay ?? 1}
        onClose={() => setEditorDay(null)}
        onAdd={(window) => setOnboarding({ windows: [...onboarding.windows, window] })}
      />
    </>
  );
}

function OnboardingThree() {
  const nav = useNav();
  const { palette } = useTheme();
  const { onboarding, session, profile, catalog, setProfile, refreshCore } = useApp();
  const [name, setName] = useState(onboarding.displayName);
  const [busy, setBusy] = useState(false);

  const locate = async () => {
    try {
      const permission = await Location.requestForegroundPermissionsAsync();
      if (permission.status !== 'granted') {
        nav.toast('Localização não autorizada.');
        return;
      }
      const position = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });
      if (session) {
        const updated = await api.profile.setRegionLocation(
          session.accessToken,
          position.coords.latitude,
          position.coords.longitude,
          8,
        );
        setProfile(updated);
      }
      nav.toast('Localização aproximada ativada.');
    } catch {
      nav.toast('Não foi possível obter a localização.');
    }
  };

  const finish = async () => {
    setBusy(true);
    try {
      if (session) {
        await api.profile.update(session.accessToken, name, null);
        const selected = onboarding.formats
          .map((item) => {
            const format = catalog
              .flatMap((sport) => sport.formats)
              .find((candidate) => candidate.name === item);
            return format
              ? {
                  format_id: format.id,
                  level: onboarding.level,
                  court_preference: onboarding.courtPreference,
                }
              : null;
          })
          .filter(
            (item): item is { format_id: string; level: string; court_preference: string } =>
              !!item,
          );
        if (selected.length > 0) {
          await api.profile.replaceSports(session.accessToken, selected);
        }
        await api.profile.replaceAvailability(session.accessToken, onboarding.windows);
        await refreshCore();
      }
    } catch {
      nav.toast('Não foi possível salvar o perfil agora.');
    } finally {
      setBusy(false);
      nav.reset('home');
    }
  };

  return (
    <Page title="Onde e como você aparece?">
      <Row between>
        <Txt variant="label">3 de 3 · região e avatar</Txt>
        <Badge>final</Badge>
      </Row>
      <Progress value={100} />
      <Card>
        <Row between>
          <Txt variant="h3">Região</Txt>
          <Badge tone="green">GPS livre</Badge>
        </Row>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 10 }}>
          <IconBtn icon="pin" label="Usar localização" ink onPress={locate} />
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 14, lineHeight: 17, fontWeight: '800', color: palette.ink }}>
              Usar localização do aparelho
            </Text>
            <Text style={{ fontSize: 13, lineHeight: 18, color: palette.muted }}>
              {profile?.region
                ? `${profile.region.city ?? 'Região'} · raio de ${profile.region.radius_km} km`
                : 'Sem região definida'}
            </Text>
          </View>
        </View>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 8 }}>
          <IconBtn icon="search" label="Buscar por CEP" toast="Busca por CEP é do passe" />
          <View style={{ flex: 1 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              <Text style={{ fontSize: 14, lineHeight: 17, fontWeight: '800', color: palette.ink }}>
                Buscar por CEP
              </Text>
              <Badge tone="blue">PASSE</Badge>
            </View>
            <Text style={{ fontSize: 13, lineHeight: 18, color: palette.muted }}>
              Disponível no plano gratuito apenas com GPS
            </Text>
          </View>
        </View>
      </Card>
      <Card>
        <Row between>
          <Txt variant="h3">Seu avatar</Txt>
          <Badge>catálogo fechado</Badge>
        </Row>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 14, marginTop: 12 }}>
          <View
            style={{
              padding: 3,
              borderWidth: 2,
              borderColor: palette.lineStrong,
              borderRadius: 60,
            }}
          >
            <Avatar size={112} {...onboarding.avatar} palette={palette} />
          </View>
          <View style={{ flex: 1 }}>
            <Text
              style={{
                fontSize: 14,
                lineHeight: 17,
                fontWeight: '800',
                color: name ? palette.ink : palette.muted,
              }}
            >
              {name || 'Seu nome'}
            </Text>
            <Text style={{ fontSize: 13, lineHeight: 18, color: palette.muted }}>
              Escolha as camadas agora. Upload de foto não existe.
            </Text>
          </View>
        </View>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 10 }}>
          <Avatar
            size={34}
            skin="#A6ABB1"
            hair="#17191B"
            shirt="#62686E"
            style={1}
            palette={palette}
          />
          <Avatar
            size={34}
            skin="#D5D9D6"
            hair="#62686E"
            shirt="#E53935"
            style={3}
            palette={palette}
          />
          <Avatar
            size={34}
            skin="#62686E"
            hair="#17191B"
            shirt="#62686E"
            style={2}
            glasses
            palette={palette}
          />
          <TextBtn go="avatar-editor">Editar camadas</TextBtn>
        </View>
      </Card>
      <Field label="Nome de exibição">
        <Input
          value={name}
          onChangeText={setName}
          maxLength={60}
          placeholder="Como os outros te veem"
        />
      </Field>
      <Notice tone="blue" icon="shield">
        Sua credencial de login verifica a conta, mas nunca aparece no perfil.
      </Notice>
      <Btn tone="primary" onPress={finish} disabled={busy}>
        {busy ? 'Salvando…' : 'Começar a jogar'}
      </Btn>
    </Page>
  );
}

function SignupPhone() {
  const nav = useNav();
  const { palette } = useTheme();
  const { auth, setAuth } = useApp();
  const [phone, setPhone] = useState('');
  const [accepted, setAccepted] = useState(true);
  const [busy, setBusy] = useState(false);

  const request = async () => {
    if (!accepted) {
      nav.toast('Aceite os termos para continuar.');
      return;
    }
    setBusy(true);
    try {
      const challenge = await api.auth.requestChallenge(
        phoneE164(phone),
        auth.purpose === 'login' ? 'login' : 'registration',
      );
      setAuth({ phone, challengeId: challenge.challenge_id });
      nav.go('otp');
    } catch (error) {
      nav.toast(errorText(error));
    } finally {
      setBusy(false);
    }
  };

  if (!authConfig.phoneEnabled) {
    return <PhoneMethodUnavailable />;
  }

  return (
    <Page title="Qual é o seu telefone?">
      <Txt variant="lead">
        Vamos enviar um código de 6 dígitos. Seu número não vira identidade pública.
      </Txt>{' '}
      <Field label="Telefone">
        <InputPrefix
          input={
            <Input
              value={phone}
              onChangeText={setPhone}
              keyboardType="phone-pad"
              maxLength={15}
              placeholder="(11) 90000-0000"
              style={{ borderWidth: 0, borderRadius: 0, minHeight: 50 }}
            />
          }
        >
          +55
        </InputPrefix>
      </Field>
      <Check checked={accepted} onChange={setAccepted}>
        Aceito os <Text style={{ fontWeight: '800', color: palette.ink }}>Termos de uso</Text> e a{' '}
        <Text style={{ fontWeight: '800', color: palette.ink }}>Política de privacidade</Text>.
      </Check>
      <TextBtn go="terms" muted>
        Ler termos de uso e política de privacidade
      </TextBtn>
      <Btn tone="primary" onPress={request} disabled={busy}>
        {busy ? 'Enviando…' : 'Receber código'}
      </Btn>
      <TextBtn
        muted
        onPress={() => {
          setAuth({ purpose: 'login' });
          nav.go('login');
        }}
      >
        Já tenho conta
      </TextBtn>
      <Notice icon="lock">Código de uso único, com prazo e limite de tentativas.</Notice>
    </Page>
  );
}

function Otp() {
  const nav = useNav();
  const { auth, setAuth, setSession, loadProfile, session, signOut } = useApp();
  const { palette } = useTheme();
  const params = nav.params;
  const phoneChange = params.phoneChange === 1;
  const challengeParam = typeof params.challengeId === 'string' ? params.challengeId : null;
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [focused, setFocused] = useState(false);
  const inputRef = useRef<ElementRef<typeof TextInput>>(null);
  const effectiveChallenge = challengeParam ?? auth.challengeId;
  const masked = useMemo(() => maskPhone(auth.phone), [auth.phone]);

  if (!authConfig.phoneEnabled) {
    return <PhoneMethodUnavailable />;
  }

  const verify = async () => {
    if (!effectiveChallenge) {
      nav.toast('Solicite um novo código para continuar.');
      nav.go('signup-phone');
      return;
    }
    if (code.length !== 6) {
      nav.toast('Digite os 6 dígitos.');
      return;
    }
    setBusy(true);
    try {
      if (phoneChange) {
        if (session) {
          await api.auth.phoneChangeConfirm(session.accessToken, effectiveChallenge, code);
          await signOut();
          nav.toast('Telefone alterado. Entre novamente.');
          nav.reset('session-expired');
        }
        return;
      }
      await api.auth.verifyChallenge(effectiveChallenge, code);
      if (auth.purpose === 'login') {
        const tokens = await api.auth.login(effectiveChallenge, {
          name: Platform.OS === 'ios' ? 'iPhone' : 'Android',
          platform: Platform.OS === 'ios' ? 'ios' : 'android',
        });
        await setSession(tokens);
        await loadProfile();
        nav.reset('home');
      } else {
        setAuth({ verifiedChallengeId: effectiveChallenge });
        nav.go('passkey');
      }
    } catch (error) {
      if (error instanceof ApiError && error.code === 'invalid_code_or_challenge') {
        nav.go('otp-error');
      } else {
        nav.toast(errorText(error));
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <Page title="Digite o código">
      <Txt variant="lead">
        Enviamos para <Text style={{ fontWeight: '800', color: palette.ink }}>{masked}</Text>.
      </Txt>
      <View style={{ position: 'relative' }}>
        <View style={{ flexDirection: 'row', justifyContent: 'center', gap: 8 }}>
          {Array.from({ length: 6 }, (_, index) => {
            const digit = code[index] ?? '';
            const active = focused && index === Math.min(code.length, 5);
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
          value={code}
          onChangeText={(value) => setCode(value.replace(/\D/g, '').slice(0, 6))}
          keyboardType="number-pad"
          textContentType="oneTimeCode"
          autoComplete="one-time-code"
          maxLength={6}
          autoFocus
          caretHidden
          accessibilityLabel="Código de verificação de 6 dígitos"
          returnKeyType="done"
          onSubmitEditing={verify}
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
      <Row between>
        <Txt variant="tiny">
          Expira em <Text style={{ fontWeight: '800', color: palette.ink }}>04:58</Text>
        </Txt>
        <TextBtn muted toast="Novo código em 42 s">
          Reenviar em 42 s
        </TextBtn>
      </Row>
      <Btn tone="primary" onPress={verify} disabled={busy || code.length !== 6}>
        {busy ? 'Verificando…' : 'Verificar'}
      </Btn>
      <TextBtn muted onPress={() => nav.go('signup-phone')}>
        Trocar número
      </TextBtn>
    </Page>
  );
}

function Passkey() {
  const nav = useNav();
  const { auth, setSession, loadProfile } = useApp();
  const [busy, setBusy] = useState(false);

  const complete = async () => {
    if (!auth.verifiedChallengeId) {
      nav.reset('onboarding-1');
      return;
    }
    setBusy(true);
    try {
      const tokens = await api.auth.register(auth.verifiedChallengeId, {
        name: Platform.OS === 'ios' ? 'iPhone' : 'Android',
        platform: Platform.OS === 'ios' ? 'ios' : 'android',
      });
      await setSession(tokens);
      try {
        if (!passkeyAvailable()) {
          throw new Error('passkey_unavailable');
        }
        const options = await api.auth.passkeyRegistrationOptions(tokens.access_token);
        const credential = await createPasskey(options.public_key);
        await api.auth.passkeyRegistrationVerify(
          tokens.access_token,
          options.challenge_id,
          credential,
          Platform.OS === 'ios' ? 'iPhone' : 'Android',
        );
      } catch {
        nav.toast(
          'Conta criada. A passkey pode ser adicionada depois em Configurações › Segurança.',
        );
      }
      await loadProfile();
      nav.reset('onboarding-1');
    } catch (error) {
      nav.toast(errorText(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Page title="Crie sua passkey">
      <StateScreen
        icon="shield"
        title={'Entre sem\ndigitar código'}
        text="Use a biometria ou o bloqueio do aparelho. A passkey fica no dispositivo e pode ser revogada depois."
      />
      <Notice tone="blue" icon="info">
        {authConfig.phoneEnabled
          ? 'Você pode usar o telefone como alternativa, mas SMS sozinho não recupera a conta.'
          : 'Você pode entrar também pelo código enviado ao seu e-mail.'}
      </Notice>
      <Btn tone="primary" icon="shield" onPress={complete} disabled={busy}>
        {busy ? 'Criando…' : 'Criar passkey'}
      </Btn>
      <Btn tone="ghost" onPress={complete} disabled={busy}>
        Agora não
      </Btn>
      <TextBtn go="passkey-unsupported" muted>
        Não consigo usar passkey neste aparelho
      </TextBtn>
    </Page>
  );
}

function Login() {
  const nav = useNav();
  const { setAuth, setSession, loadProfile } = useApp();
  const [busy, setBusy] = useState(false);

  const enterWithPasskey = async () => {
    if (busy) {
      return;
    }
    if (!passkeyAvailable()) {
      nav.toast('A passkey exige o development build Android; o módulo iOS ainda não existe.');
      return;
    }
    setBusy(true);
    try {
      const options = await api.auth.passkeyAuthenticationOptions();
      const credential = await getPasskey(options.public_key);
      const tokens = await api.auth.passkeyAuthenticationVerify(options.challenge_id, credential, {
        name: Platform.OS === 'ios' ? 'iPhone' : 'Android',
        platform: Platform.OS === 'ios' ? 'ios' : 'android',
      });
      await setSession(tokens);
      await loadProfile();
      nav.reset('home');
    } catch (error) {
      nav.toast(errorText(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Page title="Entrar">
      <Txt variant="lead">
        Use sua senha ou uma passkey. A passkey é mais rápida nas próximas vezes.
      </Txt>
      <Btn tone="primary" icon="shield" onPress={enterWithPasskey} disabled={busy}>
        {busy ? 'Abrindo…' : 'Usar passkey'}
      </Btn>
      {authConfig.emailEnabled ? (
        <Btn
          tone="ghost"
          icon="mail"
          onPress={() => {
            setAuth({ purpose: 'login' });
            nav.go('login-email');
          }}
        >
          Entrar com e-mail
        </Btn>
      ) : null}
      {authConfig.phoneEnabled ? (
        <Btn
          tone="ghost"
          icon="user"
          onPress={() => {
            setAuth({ purpose: 'login' });
            nav.go('signup-phone');
          }}
        >
          Entrar com telefone
        </Btn>
      ) : null}
      <TextBtn go="forgot-password" muted>
        Esqueci minha senha
      </TextBtn>
      <TextBtn go="recovery" muted>
        Recuperar conta
      </TextBtn>
    </Page>
  );
}

function Recovery() {
  const nav = useNav();
  const { palette } = useTheme();
  const items = [
    {
      icon: 'shield' as const,
      title: 'Usar passkey de outro dispositivo',
      sub: 'Recomendado',
      go: 'login',
    },
    ...(authConfig.emailEnabled
      ? [
          {
            icon: 'mail' as const,
            title: 'Redefinir senha por e-mail',
            sub: 'Código no endereço principal',
            go: 'forgot-password',
          },
        ]
      : []),
    ...(authConfig.phoneEnabled
      ? [
          {
            icon: 'user' as const,
            title: 'Receber código no telefone',
            sub: 'Só não basta sozinho',
            go: 'otp',
          },
        ]
      : []),
    {
      icon: 'chat' as const,
      title: 'Falar com suporte',
      sub: 'Análise de risco e auditoria',
      go: 'support',
    },
  ];
  return (
    <Page title="Recuperar conta">
      <Txt variant="lead">Se você perdeu o aparelho, ainda dá para voltar com segurança.</Txt>
      <CardList>
        {items.map((item, index) => (
          <ListRow
            key={item.title}
            onPress={() => nav.go(item.go)}
            last={index === items.length - 1}
          >
            <View style={{ width: 46, alignItems: 'center' }}>
              <IconBtn icon={item.icon} label={item.title} plain go={item.go} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                {item.title}
              </Text>
              <Text style={{ fontSize: 13, color: palette.muted, marginTop: 2 }}>{item.sub}</Text>
            </View>
            <Text style={{ color: palette.muted }}>›</Text>
          </ListRow>
        ))}
      </CardList>
      <Notice tone="red" icon="alert">
        Nunca pedimos código por telefone, chat ou e-mail fora do fluxo do app.
      </Notice>
    </Page>
  );
}

function Terms() {
  const nav = useNav();
  const { setAuth } = useApp();
  const { palette } = useTheme();
  const readOnly = nav.params.readOnly === 1;
  const [terms, setTerms] = useState<TermsVersion | null>(null);
  const [termsReady, setTermsReady] = useState(!readOnly);
  useEffect(() => {
    if (!readOnly) {
      return;
    }
    let active = true;
    api.legal
      .currentTerms()
      .then((result) => {
        if (active) {
          setTerms(result.terms);
        }
      })
      .catch(() => undefined)
      .finally(() => {
        if (active) {
          setTermsReady(true);
        }
      });
    return () => {
      active = false;
    };
  }, [readOnly]);
  const items = [
    ['O JOGA intermedeia a reserva', 'A quadra é a fornecedora; o ingresso é crédito de serviço.'],
    ['Cancelamento tem cutoff', 'Antes do cutoff, T4; depois, no-show.'],
    [
      'Devolução é em ingressos',
      'O saldo volta para seus ingressos quando a reserva não se completa.',
    ],
    ['Sem fotos de pessoas', 'Avatar de catálogo fechado; fotos só de quadras.'],
  ];
  return (
    <Page title={readOnly ? 'Termos e privacidade' : 'Antes de começar'}>
      {readOnly && termsReady ? (
        terms ? (
          <Card>
            <Row between>
              <Txt variant="h3">Termos de uso</Txt>
              <Badge tone="blue">v{terms.version}</Badge>
            </Row>
            <Text
              style={{
                marginTop: 8,
                fontSize: 13,
                lineHeight: 20,
                color: palette.ink,
              }}
            >
              {terms.content}
            </Text>
          </Card>
        ) : (
          <Notice tone="orange" icon="info">
            Nenhuma versão dos Termos foi aprovada e publicada pelo servidor ainda. Quando existir,
            o texto vigente aparece aqui e a compra de crédito exige o aceite.
          </Notice>
        )
      ) : null}
      <Card>
        <Txt variant="h3">O que você precisa saber</Txt>
        <View style={{ marginTop: 6 }}>
          {items.map(([title, sub], index) => (
            <View
              key={title}
              style={{
                flexDirection: 'row',
                alignItems: 'flex-start',
                gap: 10,
                paddingVertical: 11,
                borderBottomWidth: index === items.length - 1 ? 0 : 1,
                borderBottomColor: palette.line,
              }}
            >
              <View
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: 4,
                  backgroundColor: palette.green,
                  marginTop: 6,
                }}
              />
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>{title}</Text>
                <Text style={{ fontSize: 13, color: palette.muted, marginTop: 2 }}>{sub}</Text>
              </View>
            </View>
          ))}
        </View>
      </Card>
      {readOnly ? (
        <Btn tone="primary" back>
          Entendi
        </Btn>
      ) : (
        <>
          <Check checked>Li e aceito os Termos de uso.</Check>
          <Check checked>Li a Política de privacidade e o tratamento de localização.</Check>
          <Check>Aceito receber notificações de prazos e partidas.</Check>
          <Btn
            tone="primary"
            onPress={() => {
              setAuth({ purpose: 'registration' });
              nav.replace(authConfig.signupMethod === 'phone' ? 'signup-phone' : 'signup-email');
            }}
          >
            Aceitar e continuar
          </Btn>
          <TextBtn go="terms-privacy" muted>
            Ler termos completos
          </TextBtn>
        </>
      )}
    </Page>
  );
}

function PhoneChange() {
  const nav = useNav();
  const { session } = useApp();
  const { palette } = useTheme();
  const [phone, setPhone] = useState('');
  const [busy, setBusy] = useState(false);
  const request = async () => {
    if (!session) {
      nav.go('otp');
      return;
    }
    setBusy(true);
    try {
      const challenge = await api.auth.phoneChangeChallenge(session.accessToken, phoneE164(phone));
      nav.go('otp', { phoneChange: 1, challengeId: challenge.challenge_id });
    } catch (error) {
      nav.toast(errorText(error));
    } finally {
      setBusy(false);
    }
  };
  if (!authConfig.phoneEnabled) {
    return <PhoneMethodUnavailable />;
  }

  return (
    <Page title="Trocar telefone">
      <Card tone="flat">
        <Row between>
          <Txt variant="tiny">Telefone atual</Txt>
          <Text style={{ fontWeight: '900', color: palette.ink, fontVariant: ['tabular-nums'] }}>
            +55 (11) 9****-1234
          </Text>
        </Row>
      </Card>
      <Field label="Novo telefone">
        <InputPrefix
          input={
            <Input
              value={phone}
              onChangeText={setPhone}
              keyboardType="phone-pad"
              maxLength={15}
              placeholder="(11) 90000-0000"
              style={{ borderWidth: 0, borderRadius: 0, minHeight: 50 }}
            />
          }
        >
          +55
        </InputPrefix>
      </Field>
      <Notice tone="orange" icon="alert">
        Depois da confirmação, todas as sessões serão encerradas, inclusive esta.
      </Notice>
      <Btn tone="primary" onPress={request} disabled={busy}>
        {busy ? 'Enviando…' : 'Enviar código ao novo número'}
      </Btn>
    </Page>
  );
}

function SessionExpired() {
  return (
    <Page title="Sessão" back={false}>
      <StateScreen
        icon="lock"
        title="Sessão encerrada"
        text={
          authConfig.emailEnabled
            ? 'Por segurança, sua sessão expirou. Entre novamente com passkey ou e-mail.'
            : 'Por segurança, sua sessão expirou. Entre novamente com passkey.'
        }
        actions={
          <>
            <Btn tone="primary" go="login">
              Entrar novamente
            </Btn>
            <Btn tone="ghost" go="welcome">
              Voltar ao início
            </Btn>
          </>
        }
      />
    </Page>
  );
}

function PasskeyUnsupported() {
  return (
    <Page title="Passkey">
      <StateScreen
        icon="shield"
        title="Este aparelho não suporta passkey"
        text={
          authConfig.emailEnabled
            ? 'Você pode entrar com o e-mail e configurar uma passkey em outro dispositivo depois.'
            : 'Você pode entrar com o telefone e configurar uma passkey em outro dispositivo depois.'
        }
        actions={
          <>
            <Btn tone="primary" go={authConfig.emailEnabled ? 'login-email' : 'login'}>
              {authConfig.emailEnabled ? 'Entrar com e-mail' : 'Entrar'}
            </Btn>
            <Btn tone="ghost" go="support">
              Falar com suporte
            </Btn>
          </>
        }
      />
    </Page>
  );
}

function OtpError() {
  return (
    <Page title="Código">
      <StateScreen
        icon="alert"
        title="Código expirado"
        text="O código anterior não vale mais. Peça um novo código. Não pedimos código por telefone ou chat."
        actions={
          <>
            <Btn tone="primary" go="signup-phone">
              Pedir novo código
            </Btn>
            <Btn tone="ghost" go="login">
              Voltar para entrar
            </Btn>
          </>
        }
      />
    </Page>
  );
}

export const entranceScreens: ScreenDef[] = [
  { id: 'welcome', render: () => <Welcome /> },
  { id: 'onboarding-1', render: () => <OnboardingOne /> },
  { id: 'onboarding-2', render: () => <OnboardingTwo /> },
  { id: 'onboarding-3', render: () => <OnboardingThree /> },
  { id: 'signup-phone', render: () => <SignupPhone /> },
  { id: 'otp', render: () => <Otp /> },
  { id: 'passkey', render: () => <Passkey /> },
  { id: 'login', render: () => <Login /> },
  { id: 'recovery', render: () => <Recovery /> },
  { id: 'terms', render: () => <Terms /> },
  { id: 'phone-change', render: () => <PhoneChange /> },
  { id: 'session-expired', render: () => <SessionExpired /> },
  { id: 'passkey-unsupported', render: () => <PasskeyUnsupported /> },
  { id: 'otp-error', render: () => <OtpError /> },
];
