import * as Notifications from 'expo-notifications';
import { AndroidImportance } from 'expo-notifications';
import { Platform } from 'react-native';

/**
 * Ponto único de notificações do app do jogador.
 *
 * Cobre apenas o cliente: handler em primeiro plano, canal Android, token FCM
 * do dispositivo e o gancho de deep link por `kind`/`data`. O envio remoto e o
 * cadastro do token no backend ficam fora deste módulo.
 */

/** Canal único enquanto não houver preferências de notificação no app. */
export const DEFAULT_CHANNEL_ID = 'default';

/** Atraso do teste local: dá tempo do app abrir e do canal existir. */
const TEST_DELAY_SECONDS = 6;

let handlerConfigured = false;
let channelConfigured = false;
let registration: Promise<string | null> | null = null;
let testScheduled = false;

/** Mostra alerta e som mesmo com o app em primeiro plano. */
export function configureNotifications(): void {
  if (handlerConfigured) {
    return;
  }
  handlerConfigured = true;
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowBanner: true,
      shouldShowList: true,
      shouldPlaySound: true,
      shouldSetBadge: false,
    }),
  });
}

async function ensureDefaultChannel(): Promise<void> {
  if (Platform.OS !== 'android' || channelConfigured) {
    return;
  }
  await Notifications.setNotificationChannelAsync(DEFAULT_CHANNEL_ID, {
    name: 'Padrão',
    description: 'Convites, avisos de partida e novidades do JOGA.',
    importance: AndroidImportance.MAX,
    sound: 'default',
    vibrationPattern: [0, 250, 250, 250],
    lightColor: '#C8F04B',
  });
  channelConfigured = true;
}

/**
 * Pede permissão (Android 13+) e obtém o token FCM do dispositivo.
 *
 * A promessa fica memorizada: mesmo com falha, não há novo pedido de permissão
 * em loop. O valor do token nunca é impresso — só o tamanho, para diagnóstico.
 */
export function registerForPushNotificationsAsync(): Promise<string | null> {
  if (registration) {
    return registration;
  }
  registration = (async () => {
    await ensureDefaultChannel();

    const current = await Notifications.getPermissionsAsync();
    let status = current.status;
    if (status !== 'granted') {
      const requested = await Notifications.requestPermissionsAsync();
      status = requested.status;
    }
    if (status !== 'granted') {
      console.warn('[push] permissão de notificação não concedida');
      return null;
    }

    const device = await Notifications.getDevicePushTokenAsync();
    const token = typeof device.data === 'string' ? device.data : '';
    if (!token) {
      console.warn('[push] token FCM vazio');
      return null;
    }
    console.warn(`[push] token FCM obtido (${token.length} caracteres)`);
    return token;
  })().catch((error: unknown) => {
    console.warn('[push] registro indisponível:', error instanceof Error ? error.message : 'erro');
    return null;
  });
  return registration;
}

/**
 * Agenda uma notificação local única para provar o canal `default`.
 *
 * Fora de `__DEV__`, só roda em build de prova com
 * `EXPO_PUBLIC_NOTIFICATION_TEST=1`, para não poluir builds de demonstração.
 */
export async function scheduleLocalTestNotification(): Promise<void> {
  const enabled = __DEV__ || process.env.EXPO_PUBLIC_NOTIFICATION_TEST === '1';
  if (!enabled || testScheduled) {
    return;
  }
  testScheduled = true;
  await ensureDefaultChannel();
  await Notifications.scheduleNotificationAsync({
    content: {
      title: 'JOGA',
      body: 'Notificação local de teste do canal padrão.',
      data: { kind: 'test' },
    },
    trigger: {
      type: Notifications.SchedulableTriggerInputTypes.TIME_INTERVAL,
      seconds: TEST_DELAY_SECONDS,
      channelId: DEFAULT_CHANNEL_ID,
    },
  });
  console.warn('[push] notificação local de teste agendada');
}

export type NotificationRouteParams = Record<string, string>;

export type NotificationRoute = {
  screen: string;
  params: NotificationRouteParams;
};

export type NotificationNavigator = (route: NotificationRoute) => void;

let navigator: NotificationNavigator | null = null;

/** O `Shell` registra aqui o ponto único de navegação (nada de rota solta). */
export function setNotificationNavigator(next: NotificationNavigator | null): void {
  navigator = next;
}

/** `kind` enviado pelo backend -> tela do app. `notifications` é o padrão. */
const KIND_SCREENS: Record<string, string> = {
  friend: 'friends',
  friends: 'friends',
  friendship: 'friends',
  friend_request: 'friends',
  friend_accepted: 'friends',
  amizade: 'friends',
  clan: 'clan',
  clan_invite: 'clan',
  clan_request: 'clan',
  cla: 'clan',
  clã: 'clan',
  lobby: 'lobby-detail',
  lobby_invite: 'lobby-detail',
  lobby_full: 'lobby-detail',
  lobby_canceled: 'lobby-detail',
  match: 'match-detail',
  match_result: 'match-detail',
  match_dispute: 'match-detail',
  substitute: 'match-detail',
  booking: 'booking-history',
  notification: 'notifications',
  system: 'notifications',
  test: 'notifications',
};

function text(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

/**
 * Traduz `data` da notificação em rota única do app.
 *
 * Sem navegador registrado (app ainda no boot) a rota é descartada com aviso;
 * o listener de resposta é instalado no `Shell`, onde a navegação já existe.
 */
export function routeNotification(data: unknown): NotificationRoute | null {
  if (!data || typeof data !== 'object') {
    console.warn('[push] notificação sem data; rota ignorada');
    return null;
  }
  const payload = data as Record<string, unknown>;
  const kind = (text(payload.kind) ?? text(payload.type) ?? '').toLowerCase();
  const screen = KIND_SCREENS[kind] ?? 'notifications';
  const params: NotificationRouteParams = {};

  if (screen === 'lobby-detail') {
    const lobbyId = text(payload.lobbyId) ?? text(payload.lobby_id);
    const matchId = text(payload.matchId) ?? text(payload.match_id);
    if (lobbyId) {
      params.lobbyId = lobbyId;
    } else if (matchId) {
      params.matchId = matchId;
    }
  } else if (screen === 'match-detail') {
    const matchId = text(payload.matchId) ?? text(payload.match_id);
    if (matchId) {
      params.matchId = matchId;
    }
  } else if (screen === 'clan') {
    const clanId = text(payload.clanId) ?? text(payload.clan_id);
    if (clanId) {
      params.clanId = clanId;
    }
  }

  const route: NotificationRoute = { screen, params };
  if (!navigator) {
    console.warn(`[push] navegação indisponível; rota ${screen} descartada`);
    return route;
  }
  navigator(route);
  return route;
}

/**
 * Instala o handler de toque na notificação.
 *
 * Só o listener ao vivo é usado: `getLastNotificationResponseAsync` devolveria
 * respostas antigas a cada boot e navegaria sem o usuário ter tocado.
 */
export function subscribeToNotificationResponses(): { remove: () => void } {
  const subscription = Notifications.addNotificationResponseReceivedListener((response) => {
    routeNotification(response.notification.request.content.data);
  });
  return {
    remove: () => subscription.remove(),
  };
}
