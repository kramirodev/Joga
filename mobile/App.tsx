import * as SplashScreen from 'expo-splash-screen';
import { StatusBar as ExpoStatusBar } from 'expo-status-bar';
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import {
  Animated,
  Appearance,
  BackHandler,
  Easing,
  Pressable,
  StyleSheet,
  View,
  useWindowDimensions,
} from 'react-native';
import { SafeAreaProvider, useSafeAreaInsets } from 'react-native-safe-area-context';

import { fontScaleFactor } from './src/accessibility';
import { authConfig } from './src/auth/config';
import { AppProvider, useApp } from './src/state/app';
import { Text } from './src/ui/text';
import {
  NavContext,
  ThemeContext,
  useTheme,
  type NavValue,
  type Params,
  type TabKey,
} from './src/state/context';
import { entranceScreens } from './src/screens/entrance';
import { emailScreens } from './src/screens/email';
import { coreScreens } from './src/screens/core';
import { venueScreens } from './src/screens/venues';
import { walletScreens } from './src/screens/wallet';
import { seasonScreens } from './src/screens/season';
import { statsScreens } from './src/screens/stats';
import { socialScreens } from './src/screens/social';
import { systemScreens } from './src/screens/system';
import type { ScreenDef } from './src/screens/types';
import { api, ApiError } from './src/api/client';
import {
  Badge,
  Btn,
  BtnRow,
  Card,
  ChipRow,
  Field,
  Kv,
  Notice,
  Page,
  Row,
  StateScreen,
  Textarea,
  Txt,
} from './src/ui/kit';
import { shortDateTime } from './src/ui/datetime';
import { BrandLoader } from './src/ui/BrandLoader';
import { BottomSheetFrame, useSheetClose } from './src/ui/BottomSheetFrame';
import { QueueIndicator } from './src/ui/QueueIndicator';
import { dark, light } from './src/ui/theme';
import { Icon } from './src/ui/icons';

// Mantém o splash nativo até fontes e sessão estarem prontas, para não haver
// flash branco entre o splash e o loader.
SplashScreen.preventAutoHideAsync().catch(() => undefined);

const ALL_SCREENS: ScreenDef[] = [
  ...entranceScreens,
  ...emailScreens,
  ...coreScreens,
  ...venueScreens,
  ...walletScreens,
  ...seasonScreens,
  ...statsScreens,
  ...socialScreens,
  ...systemScreens,
].filter((screen) => !screen.hidden);

const REGISTRY: Record<string, ScreenDef> = Object.fromEntries(
  ALL_SCREENS.map((screen) => [screen.id, screen]),
);

const TABS: { key: TabKey; label: string; icon: 'home' | 'cal' | 'trophy' | 'users' | 'user' }[] = [
  { key: 'jogar', label: 'Jogar', icon: 'home' },
  { key: 'partidas', label: 'Partidas', icon: 'cal' },
  { key: 'temporada', label: 'Temporada', icon: 'trophy' },
  { key: 'social', label: 'Social', icon: 'users' },
  { key: 'perfil', label: 'Perfil', icon: 'user' },
];

const TAB_ROOT: Record<TabKey, string> = {
  jogar: 'home',
  partidas: 'matches',
  temporada: 'season',
  social: 'friends',
  perfil: 'profile-me',
};

type StackEntry = { id: string; params: Params };

function TabButton({
  active,
  label,
  icon,
  onPress,
}: {
  active: boolean;
  label: string;
  icon: 'home' | 'cal' | 'trophy' | 'users' | 'user';
  onPress: () => void;
}) {
  const { palette, largeTargets } = useTheme();
  const [focus] = useState(() => new Animated.Value(active ? 1 : 0));

  useEffect(() => {
    Animated.spring(focus, {
      toValue: active ? 1 : 0,
      useNativeDriver: true,
      speed: 22,
      bounciness: 0,
    }).start();
  }, [active, focus]);

  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ selected: active }}
      style={({ pressed }) => ({
        flex: 1,
        minHeight: largeTargets ? 56 : 48,
        borderRadius: 12,
        alignItems: 'center',
        justifyContent: 'center',
        gap: 1,
        opacity: pressed ? 0.86 : 1,
        transform: pressed ? [{ scale: 0.97 }] : [],
      })}
    >
      <Animated.View
        pointerEvents="none"
        style={{
          position: 'absolute',
          top: 0,
          left: '26%',
          right: '26%',
          height: 3,
          borderBottomLeftRadius: 3,
          borderBottomRightRadius: 3,
          backgroundColor: palette.lime,
          opacity: focus,
          transform: [
            {
              scaleX: focus.interpolate({ inputRange: [0, 1], outputRange: [0.55, 1] }),
            },
          ],
        }}
      />
      <Animated.View
        style={{
          transform: [
            {
              scale: focus.interpolate({ inputRange: [0, 1], outputRange: [1, 1.08] }),
            },
          ],
        }}
      >
        <Icon name={icon} size={19} color={active ? palette.lime : palette.muted} />
      </Animated.View>
      <Text
        numberOfLines={1}
        adjustsFontSizeToFit
        minimumFontScale={0.75}
        maxFontSizeMultiplier={1.2}
        style={{
          fontSize: 11,
          lineHeight: 13,
          fontWeight: '800',
          letterSpacing: 0.2,
          color: active ? palette.ink : palette.muted,
        }}
      >
        {label}
      </Text>
    </Pressable>
  );
}

function TabBar({
  tab,
  onSelect,
  bottomInset,
}: {
  tab: TabKey;
  onSelect: (tab: TabKey) => void;
  bottomInset: number;
}) {
  const { palette } = useTheme();
  const paddingBottom = Math.max(0, bottomInset);
  return (
    <View style={{ flexShrink: 0, backgroundColor: palette.bg }}>
      <View
        style={{
          minHeight: 54,
          borderTopWidth: 1.5,
          borderTopColor: palette.line,
          backgroundColor: palette.surface,
          flexDirection: 'row',
          gap: 3,
          paddingTop: 3,
          paddingHorizontal: 5,
          paddingBottom: 3,
        }}
      >
        {TABS.map((item) => (
          <TabButton
            key={item.key}
            active={item.key === tab}
            label={item.label}
            icon={item.icon}
            onPress={() => onSelect(item.key)}
          />
        ))}
      </View>
      {paddingBottom > 0 ? (
        <View style={{ height: paddingBottom, backgroundColor: palette.bg }} />
      ) : null}
    </View>
  );
}

function Sheet({
  id,
  onClose,
  onConfirm,
}: {
  id: string;
  onClose: () => void;
  onConfirm: () => void;
}) {
  const { palette } = useAppTheme();
  const content: Record<
    string,
    { title: string; text: string; cancel: string; confirm: string; danger?: boolean }
  > = {
    confirm: {
      title: 'Confirmar ação?',
      text: 'Esta ação não pode ser desfeita.',
      cancel: 'Voltar',
      confirm: 'Confirmar',
      danger: true,
    },
    'cancel-booking': {
      title: 'Cancelar reserva?',
      text: 'A política de cancelamento da quadra será aplicada. Vagas já pagas podem virar crédito, conforme a antecedência.',
      cancel: 'Manter reserva',
      confirm: 'Cancelar reserva',
      danger: true,
    },
    cancel: {
      title: 'Cancelar participação?',
      text: 'Você recusa a participação. Se a reserva já existe, o cutoff decide: antes dele há devolução integral em ingressos; depois dele não há devolução e um substituto pode ocupar a vaga.',
      cancel: 'Manter vaga',
      confirm: 'Cancelar participação',
      danger: true,
    },
    logout: {
      title: 'Sair da conta?',
      text: authConfig.emailEnabled
        ? 'Você precisará da passkey ou do e-mail para entrar de novo.'
        : 'Você precisará da passkey ou do telefone para entrar de novo.',
      cancel: 'Ficar',
      confirm: 'Sair',
      danger: true,
    },
    block: {
      title: 'Bloquear jogador?',
      text: 'Amizade, convites e eventos sociais serão cortados. O outro jogador não vê o motivo.',
      cancel: 'Voltar',
      confirm: 'Bloquear',
      danger: true,
    },
    filter: {
      title: 'Filtrar quadras',
      text: 'Filtros são preferências, nunca anúncios.',
      cancel: 'Voltar',
      confirm: 'Aplicar filtros',
    },
    share: {
      title: 'Compartilhar',
      text: 'Envie a referência de partida, quadra ou lobby para quem você quiser.',
      cancel: 'Voltar',
      confirm: 'Copiar link do JOGA',
    },
  };
  const item = content[id] ?? content.confirm;

  return (
    <BottomSheetFrame
      visible
      onClose={onClose}
      title={item.title}
      subtitle={item.text}
      accessibilityLabel={item.title}
      footer={<SheetActions item={item} onConfirm={onConfirm} />}
    >
      {id === 'filter' ? (
        <View style={{ marginBottom: 12 }}>
          <ChipRow>
            <Badge>Futebol 5x5</Badge>
            <Badge>Vôlei 6x6</Badge>
            <Badge>Coberta</Badge>
            <Badge>Até 10 km</Badge>
          </ChipRow>
        </View>
      ) : null}
      {id === 'share' ? (
        <Card tone="flat">
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <Icon name="cal" size={16} color={palette.ink} />
            <Txt variant="tiny">Partida, quadra ou referência do JOGA</Txt>
          </View>
        </Card>
      ) : null}
    </BottomSheetFrame>
  );
}

/** Botões do sheet compartilhado; usam o fechamento animado do frame. */
function SheetActions({
  item,
  onConfirm,
}: {
  item: { cancel: string; confirm: string; danger?: boolean };
  onConfirm: () => void;
}) {
  const close = useSheetClose();
  return (
    <BtnRow>
      <Btn tone="ghost" onPress={() => close()}>
        {item.cancel}
      </Btn>
      <Btn tone={item.danger ? 'danger' : 'primary'} onPress={() => close(onConfirm)}>
        {item.confirm}
      </Btn>
    </BtnRow>
  );
}

function useAppTheme() {
  const app = useApp();
  const palette = app.dark ? dark : light;
  return { palette, dark: app.dark };
}

type TabStacks = Record<TabKey, StackEntry[]>;
type ScreenPhase = 'idle' | 'enter' | 'exit';
type ScreenMotion = 'push' | 'pop' | 'tab';

function createStacks(signedIn: boolean): TabStacks {
  return {
    jogar: [{ id: signedIn ? 'home' : 'welcome', params: {} }],
    partidas: [{ id: 'matches', params: {} }],
    temporada: [{ id: 'season', params: {} }],
    social: [{ id: 'friends', params: {} }],
    perfil: [{ id: 'profile-me', params: {} }],
  };
}

function entryKey(entry: StackEntry): string {
  const keys = Object.keys(entry.params ?? {}).sort();
  if (keys.length === 0) {
    return entry.id;
  }
  return `${entry.id}?${keys.map((key) => `${key}=${String(entry.params[key])}`).join('&')}`;
}

/** Rotas de compra de ingressos mantidas no código, mas sem caminho alcançável. */
const PURCHASE_ROUTES = new Set(['store', 'checkout-package', 'buy-3']);

function PurchaseUnavailable() {
  return (
    <Page title="Ingressos">
      <StateScreen
        icon="wallet"
        title="Compra de ingressos indisponível"
        text="A compra de ingressos está desativada nesta versão do JOGA. Seus ingressos atuais continuam válidos e podem ser usados normalmente nas reservas."
        actions={
          <Btn tone="primary" back>
            Voltar
          </Btn>
        }
      />
    </Page>
  );
}

function ScreenLayer({ entry }: { entry: StackEntry }) {
  if (PURCHASE_ROUTES.has(entry.id)) {
    return <PurchaseUnavailable />;
  }
  const def = REGISTRY[entry.id] ?? REGISTRY.welcome;
  return <View style={{ flex: 1 }}>{def.render({ params: entry.params })}</View>;
}

function Toast({
  message,
  onHide,
  bottom,
}: {
  message: string;
  onHide: () => void;
  bottom: number;
}) {
  const { palette, dark } = useTheme();
  const [anim] = useState(() => new Animated.Value(0));
  const hideRef = useRef(onHide);

  useEffect(() => {
    hideRef.current = onHide;
  }, [onHide]);

  useEffect(() => {
    Animated.timing(anim, {
      toValue: 1,
      duration: 180,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: true,
    }).start();
    const timer = setTimeout(() => {
      Animated.timing(anim, {
        toValue: 0,
        duration: 160,
        easing: Easing.in(Easing.cubic),
        useNativeDriver: true,
      }).start(({ finished }) => {
        if (finished) {
          hideRef.current();
        }
      });
    }, 2000);
    return () => clearTimeout(timer);
  }, [anim]);

  return (
    <Animated.View
      pointerEvents="none"
      style={{
        position: 'absolute',
        left: 20,
        right: 20,
        bottom,
        alignItems: 'center',
        opacity: anim,
        transform: [{ translateY: anim.interpolate({ inputRange: [0, 1], outputRange: [12, 0] }) }],
      }}
    >
      <View
        style={{
          backgroundColor: dark ? palette.lime : palette.ink,
          borderRadius: 10,
          paddingHorizontal: 16,
          paddingVertical: 11,
          maxWidth: '100%',
        }}
      >
        <Text
          maxFontSizeMultiplier={1.3}
          style={{
            fontSize: 13,
            fontWeight: '700',
            color: palette.onInk,
            textAlign: 'center',
          }}
        >
          {message}
        </Text>
      </View>
    </Animated.View>
  );
}

function appealBadge(status: string): {
  label: string;
  tone: 'blue' | 'green' | 'orange' | 'red';
} {
  if (status === 'ACCEPTED') {
    return { label: 'ACEITO', tone: 'green' };
  }
  if (status === 'REJECTED') {
    return { label: 'REJEITADO', tone: 'red' };
  }
  return { label: 'EM ANÁLISE', tone: 'orange' };
}

function UpdateRequiredScreen() {
  return (
    <Page title="Atualize o JOGA" back={false}>
      <StateScreen
        icon="download"
        title="Atualização obrigatória"
        text="Esta versão do JOGA não é mais suportada. Atualize pelo canal de distribuição para continuar usando o aplicativo."
      />
    </Page>
  );
}

function SuspendedScreen() {
  const app = useApp();
  const { palette } = useTheme();
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<{ text: string; tone: 'green' | 'orange' } | null>(null);
  const attempted = useRef(false);
  const suspension =
    app.moderationActions.find(
      (action) => action.action_type === 'SUSPEND_TEMP' && action.status === 'ACTIVE',
    ) ?? app.moderationActions.find((action) => action.action_type === 'SUSPEND_TEMP');
  const appeal = suspension
    ? (app.moderationAppeals.find((item) => item.action_id === suspension.id) ?? null)
    : null;
  const appealState = appeal ? appealBadge(appeal.status) : null;

  useEffect(() => {
    if (attempted.current) {
      return;
    }
    attempted.current = true;
    // Revalida a suspensão ao abrir a tela: a conta pode ter sido reativada
    // enquanto o app estava fechado ou em segundo plano.
    void app.recheckSuspension();
  }, [app]);

  const reloadModeration = () =>
    Promise.allSettled([app.loadModerationActions(), app.loadModerationAppeals()]);

  const submit = async () => {
    if (!app.session || !suspension || busy) {
      return;
    }
    if (!text.trim()) {
      setFeedback({ text: 'Explique o motivo do recurso.', tone: 'orange' });
      return;
    }
    setBusy(true);
    setFeedback(null);
    try {
      await api.moderation.appeal(app.session.accessToken, suspension.id, text.trim());
      setFeedback({ text: 'Recurso enviado. A análise é interna.', tone: 'green' });
      setText('');
      await reloadModeration();
    } catch (error) {
      const messages: Record<string, string> = {
        account_suspended:
          'O recurso não pôde ser enviado enquanto a suspensão está ativa. Fale com o suporte.',
        appeal_already_exists: 'Você já enviou um recurso para esta medida.',
        action_not_active: 'Esta medida não está mais ativa.',
        not_found: 'Medida não encontrada.',
        forbidden: 'Você não pode recorrer desta medida.',
      };
      setFeedback({
        text:
          error instanceof ApiError
            ? (messages[error.code] ?? 'Não foi possível enviar o recurso.')
            : 'Não foi possível enviar o recurso.',
        tone: 'orange',
      });
      if (
        error instanceof ApiError &&
        (error.code === 'appeal_already_exists' || error.code === 'action_not_active')
      ) {
        await reloadModeration();
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <Page title="Conta suspensa" back={false}>
      <StateScreen
        icon="lock"
        title="Conta temporariamente suspensa"
        text="Seu acesso a partidas e recursos está pausado, mas sua conta, histórico e saldo continuam preservados."
      />
      {suspension ? (
        <Card tone="orange">
          <Row between>
            <Badge tone="orange">MEDIDA ATIVA</Badge>
            <Badge>ATIVA</Badge>
          </Row>
          <Txt variant="h3" style={{ marginTop: 10 }}>
            Suspensão temporária
          </Txt>
          <View
            style={{
              marginTop: 6,
              paddingTop: 9,
              paddingBottom: 9,
              borderBottomWidth: 1,
              borderBottomColor: palette.line,
            }}
          >
            <Text
              style={{
                fontSize: 12,
                fontWeight: '800',
                letterSpacing: 0.4,
                textTransform: 'uppercase',
                color: palette.muted,
              }}
            >
              Motivo
            </Text>
            <Text style={{ fontSize: 14, lineHeight: 20, color: palette.ink, marginTop: 2 }}>
              {suspension.reason}
            </Text>
          </View>
          <Kv label="Início" value={shortDateTime(suspension.starts_at)} />
          <Kv
            label="Fim previsto"
            value={suspension.ends_at ? shortDateTime(suspension.ends_at) : 'Sem prazo'}
          />
        </Card>
      ) : (
        <Notice tone="orange" icon="alert">
          O motivo detalhado aparece aqui quando a medida estiver sincronizada. Enquanto isso, use o
          suporte para contestar.
        </Notice>
      )}
      {appeal ? (
        <Card>
          <Row between>
            <Txt variant="h3">Seu recurso</Txt>
            <Badge tone={appealState?.tone}>{appealState?.label}</Badge>
          </Row>
          <Text style={{ fontSize: 14, lineHeight: 20, color: palette.ink, marginTop: 8 }}>
            {appeal.reason}
          </Text>
          <Kv label="Enviado em" value={shortDateTime(appeal.created_at)} />
          {appeal.decided_at ? (
            <Kv label="Decidido em" value={shortDateTime(appeal.decided_at)} />
          ) : null}
          {appeal.status === 'OPEN' ? (
            <Notice tone="blue" icon="info">
              Recurso em análise. A decisão aparecerá aqui.
            </Notice>
          ) : null}
          {appeal.status === 'ACCEPTED' ? (
            <Notice tone="green" icon="shield">
              Recurso aceito. A medida foi revista.
            </Notice>
          ) : null}
          {appeal.status === 'REJECTED' ? (
            <>
              <Notice tone="orange" icon="alert">
                A medida foi mantida.
              </Notice>
              {appeal.decision_reason ? (
                <View style={{ marginTop: 10 }}>
                  <Text
                    style={{
                      fontSize: 12,
                      fontWeight: '800',
                      letterSpacing: 0.4,
                      textTransform: 'uppercase',
                      color: palette.muted,
                    }}
                  >
                    Justificativa
                  </Text>
                  <Text style={{ fontSize: 14, lineHeight: 20, color: palette.ink, marginTop: 2 }}>
                    {appeal.decision_reason}
                  </Text>
                </View>
              ) : null}
            </>
          ) : null}
        </Card>
      ) : suspension ? (
        <>
          <Field label="Recurso">
            <Textarea
              value={text}
              onChangeText={setText}
              maxLength={1000}
              placeholder="Explique por que a medida deve ser revista."
            />
          </Field>
          <Btn tone="primary" onPress={submit} disabled={busy || !text.trim()}>
            {busy ? 'Enviando…' : 'Enviar recurso'}
          </Btn>
        </>
      ) : null}
      {feedback ? (
        <Notice tone={feedback.tone} icon="info">
          {feedback.text}
        </Notice>
      ) : null}
      <Notice tone="blue" icon="shield">
        A triagem é interna. O alvo não vê quem denunciou e a severidade não é exposta.
      </Notice>
      <Btn tone="primary" onPress={() => app.recheckSuspension()}>
        Tentar novamente
      </Btn>
      <Btn tone="ghost" onPress={() => app.signOut()}>
        Sair da conta
      </Btn>
    </Page>
  );
}

function Shell() {
  const app = useApp();
  const signedIn = !!app.session;
  const [tabStacks, setTabStacks] = useState<TabStacks>(() => createStacks(signedIn));
  const [tab, setTab] = useState<TabKey>('jogar');
  const [modal, setModal] = useState<{ id: string; onConfirm?: () => void } | null>(null);
  const [toast, setToast] = useState<{ message: string; id: number } | null>(null);
  const toastSeq = useRef(0);
  const signedInRef = useRef(signedIn);
  const tabRef = useRef<TabKey>(tab);
  const phaseRef = useRef<ScreenPhase>('idle');
  const transitionId = useRef(0);
  const [phase, setPhase] = useState<ScreenPhase>('idle');
  const [motion, setMotion] = useState<ScreenMotion>('push');
  const palette = app.dark ? dark : light;
  const reducedMotion = app.accessibility.reducedMotion;
  const { width: screenWidth } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const statusInset = insets.top;

  const stack = tabStacks[tab];
  const current = useMemo(
    () => stack[stack.length - 1] ?? { id: signedIn ? 'home' : 'welcome', params: {} },
    [stack, signedIn],
  );
  const screen = REGISTRY[current.id] ?? REGISTRY.welcome;
  const showTabBar = !app.suspended && signedIn && !!screen.tab;
  const canGoBack = stack.length > 1 && !app.suspended;
  const showQueueIndicator =
    !app.suspended &&
    signedIn &&
    current.id !== 'queue' &&
    current.id !== 'queue-search' &&
    (app.queue.length > 0 || app.matchedEntry !== null || app.queueNotice !== null);
  const toastBottom = (showTabBar ? 80 : 20) + insets.bottom;
  // Fonte única do inset inferior: a tab bar já reserva o espaço do sistema.
  const contentBottomInset = showTabBar ? 0 : insets.bottom;

  const [anim] = useState(() => new Animated.Value(1));

  useEffect(() => {
    tabRef.current = tab;
  }, [tab]);

  useEffect(() => {
    Appearance.setColorScheme(app.dark ? 'dark' : 'light');
  }, [app.dark]);

  const splashHidden = useRef(false);
  useEffect(() => {
    const hideSplash = () => {
      if (splashHidden.current) {
        return;
      }
      splashHidden.current = true;
      SplashScreen.hideAsync().catch(() => undefined);
    };
    if (app.ready) {
      hideSplash();
    }
    // Guarda contra refresh/sessão pendurados: o splash nunca fica eterno.
    // O loader escuro continua por baixo enquanto o app termina de hidratar.
    const guard = setTimeout(() => {
      if (!splashHidden.current && __DEV__) {
        console.warn('[brand] splash liberado pelo guarda de 9 s sem app.ready.');
      }
      hideSplash();
    }, 9_000);
    return () => clearTimeout(guard);
  }, [app.ready]);

  useLayoutEffect(() => {
    if (!app.ready || signedInRef.current === signedIn) {
      return;
    }
    signedInRef.current = signedIn;
    transitionId.current += 1;
    phaseRef.current = 'idle';
    setPhase('idle');
    anim.setValue(1);
    setTab('jogar');
    setTabStacks(createStacks(signedIn));
  }, [app.ready, signedIn, anim]);

  const beginTransition = useCallback(
    (nextPhase: ScreenPhase, nextMotion: ScreenMotion, onComplete?: () => void) => {
      transitionId.current += 1;
      const id = transitionId.current;
      phaseRef.current = nextPhase;
      setPhase(nextPhase);
      setMotion(nextMotion);
      anim.setValue(0);
      requestAnimationFrame(() => {
        if (id !== transitionId.current) {
          return;
        }
        const run = Animated.timing(anim, {
          toValue: 1,
          duration: reducedMotion ? 0 : nextMotion === 'tab' ? 180 : 240,
          easing: Easing.out(Easing.cubic),
          useNativeDriver: true,
        });
        run.start(({ finished }) => {
          if (!finished || id !== transitionId.current) {
            return;
          }
          phaseRef.current = 'idle';
          setPhase('idle');
          anim.setValue(1);
          onComplete?.();
        });
      });
    },
    [anim, reducedMotion],
  );

  const nav = useMemo<NavValue>(
    () => ({
      id: current.id,
      tab: screen.tab ?? tab,
      params: current.params,
      canGoBack,
      go: (id, params) => {
        setTabStacks((previous) => ({
          ...previous,
          [tab]: [...previous[tab], { id, params: params ?? {} }],
        }));
        beginTransition('enter', 'push');
      },
      replace: (id, params) => {
        setTabStacks((previous) => ({
          ...previous,
          [tab]: [...previous[tab].slice(0, -1), { id, params: params ?? {} }],
        }));
        beginTransition('enter', 'push');
      },
      reset: (id, params) => {
        const nextTab = REGISTRY[id]?.tab ?? tab;
        setTab(nextTab);
        setTabStacks((previous) => ({
          ...previous,
          [nextTab]: [{ id, params: params ?? {} }],
        }));
        beginTransition('enter', 'tab');
      },
      back: () => {
        if (phaseRef.current !== 'idle' || stack.length <= 1) {
          return;
        }
        const activeTab = tab;
        beginTransition('exit', 'pop', () => {
          if (tabRef.current !== activeTab) {
            return;
          }
          setTabStacks((previous) => {
            const active = previous[activeTab];
            if (active.length <= 1) {
              return previous;
            }
            return { ...previous, [activeTab]: active.slice(0, -1) };
          });
        });
      },
      tabTo: (next) => {
        if (next === tab) {
          setTabStacks((previous) => ({
            ...previous,
            [tab]: [{ id: TAB_ROOT[tab], params: {} }],
          }));
          beginTransition('enter', 'tab');
          return;
        }
        setTab(next);
        beginTransition('enter', 'tab');
      },
      openModal: (id, onConfirm) => setModal({ id, onConfirm }),
      toast: (message) => {
        toastSeq.current += 1;
        setToast({ message, id: toastSeq.current });
      },
    }),
    [current.id, current.params, tab, canGoBack, screen.tab, stack.length, beginTransition],
  );

  useEffect(() => {
    const subscription = BackHandler.addEventListener('hardwareBackPress', () => {
      if (modal) {
        setModal(null);
        return true;
      }
      if (canGoBack) {
        nav.back();
        return true;
      }
      return false;
    });
    return () => subscription.remove();
  }, [modal, canGoBack, nav]);

  const theme = useMemo(
    () => ({
      palette,
      dark: app.dark,
      setDark: app.setDark,
      fontScale: fontScaleFactor(app.accessibility.fontScale),
      largeTargets: app.accessibility.largeTargets,
      contentBottomInset,
    }),
    [palette, app.dark, app.setDark, app.accessibility, contentBottomInset],
  );

  const confirmModal = () => {
    const active = modal;
    if (!active) {
      return;
    }
    setModal(null);
    if (active.id === 'logout') {
      app.signOut().then(() => {
        setTab('jogar');
        setTabStacks(createStacks(false));
      });
      return;
    }
    if (active.onConfirm) {
      active.onConfirm();
      return;
    }
    const messages: Record<string, string> = {
      cancel: 'Participação cancelada.',
      block: 'Bloqueio ainda não disponível no app.',
      filter: 'Filtros ainda não disponíveis no app.',
      share: 'Compartilhamento ainda não disponível no app.',
      confirm: 'Ação ainda não disponível no app.',
    };
    nav.toast(messages[active.id] ?? 'Ação ainda não disponível no app.');
  };

  const topStyle =
    phase === 'idle'
      ? undefined
      : motion === 'tab'
        ? {
            transform: [
              { translateY: anim.interpolate({ inputRange: [0, 1], outputRange: [8, 0] }) },
            ],
          }
        : phase === 'exit'
          ? {
              transform: [
                {
                  translateX: anim.interpolate({
                    inputRange: [0, 1],
                    outputRange: [0, screenWidth],
                  }),
                },
              ],
            }
          : {
              transform: [
                {
                  translateX: anim.interpolate({
                    inputRange: [0, 1],
                    outputRange: [screenWidth, 0],
                  }),
                },
              ],
            };

  if (!app.ready) {
    return (
      <ThemeContext.Provider value={theme}>
        <ExpoStatusBar style="light" />
        <BrandLoader />
      </ThemeContext.Provider>
    );
  }

  return (
    <ThemeContext.Provider value={theme}>
      <NavContext.Provider value={nav}>
        <ExpoStatusBar style={app.dark ? 'light' : 'dark'} />
        <View
          style={{
            flex: 1,
            backgroundColor: palette.bg,
            paddingTop: statusInset,
          }}
        >
          <View style={{ flex: 1 }}>
            <View style={{ flex: 1, overflow: 'hidden', backgroundColor: palette.bg }}>
              {app.updateRequired ? (
                <UpdateRequiredScreen />
              ) : app.suspended ? (
                <SuspendedScreen />
              ) : (
                stack.map((entry, index) => {
                  const isTop = index === stack.length - 1;
                  return (
                    <Animated.View
                      key={entryKey(entry)}
                      pointerEvents={isTop && phase !== 'exit' ? 'auto' : 'none'}
                      style={[
                        StyleSheet.absoluteFill,
                        { zIndex: index + 1 },
                        isTop ? topStyle : null,
                      ]}
                    >
                      <ScreenLayer entry={entry} />
                    </Animated.View>
                  );
                })
              )}
            </View>
            {showQueueIndicator ? <QueueIndicator /> : null}
            {showTabBar ? (
              <TabBar tab={tab} onSelect={nav.tabTo} bottomInset={insets.bottom} />
            ) : null}
          </View>
          {toast ? (
            <Toast
              key={toast.id}
              message={toast.message}
              bottom={toastBottom}
              onHide={() =>
                setToast((currentToast) => (currentToast?.id === toast.id ? null : currentToast))
              }
            />
          ) : null}
        </View>
        {modal ? (
          <Sheet id={modal.id} onClose={() => setModal(null)} onConfirm={confirmModal} />
        ) : null}
      </NavContext.Provider>
    </ThemeContext.Provider>
  );
}

export default function App() {
  return (
    <SafeAreaProvider>
      <AppProvider>
        <Shell />
      </AppProvider>
    </SafeAreaProvider>
  );
}
