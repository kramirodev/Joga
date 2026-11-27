import * as Notifications from 'expo-notifications';
import { AndroidImportance } from 'expo-notifications';
import { Platform } from 'react-native';

import { notificationRouteFor, type NotificationRoute } from './state/notificationRoutes';

export type { NotificationRoute, NotificationRouteParams } from './state/notificationRoutes';

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

export type NotificationNavigator = (route: NotificationRoute) => void;

let navigator: NotificationNavigator | null = null;

/** O `Shell` registra aqui o ponto único de navegação (nada de rota solta). */
export function setNotificationNavigator(next: NotificationNavigator | null): void {
  navigator = next;
}

/** Resposta que abriu o app; consumida uma única vez depois do boot. */
let coldStartResponse: Notifications.NotificationResponse | null = null;
let coldStartCaptured = false;
let coldStartRouted = false;

/** Evita navegar duas vezes quando o listener e o cold start veem o mesmo toque. */
let lastRoutedIdentifier: string | null = null;

/**
 * Guarda a resposta que abriu o app e limpa o cache nativo.
 *
 * Chamado antes de instalar o listener ao vivo, para que só o toque de abertura
 * vire cold start. `clearLastNotificationResponse` impede que ele seja repetido
 * no próximo boot.
 */
function captureColdStartResponse(): void {
  if (coldStartCaptured) {
    return;
  }
  coldStartCaptured = true;
  try {
    const response = Notifications.getLastNotificationResponse();
    if (!response) {
      return;
    }
    coldStartResponse = response;
    Notifications.clearLastNotificationResponse();
  } catch (error) {
    console.warn(
      '[push] cold start indisponível:',
      error instanceof Error ? error.message : 'erro',
    );
  }
}

function routeResponse(response: Notifications.NotificationResponse): NotificationRoute | null {
  const identifier =
    typeof response.notification.request.identifier === 'string'
      ? response.notification.request.identifier.trim()
      : '';
  if (identifier) {
    if (identifier === lastRoutedIdentifier) {
      return null;
    }
    lastRoutedIdentifier = identifier;
  }
  return routeNotification(response.notification.request.content.data);
}

/**
 * Traduz `data` da notificação em rota única do app.
 *
 * Sem navegador registrado (app ainda no boot) a rota é descartada com aviso;
 * o listener de resposta é instalado no `Shell`, onde a navegação já existe.
 */
export function routeNotification(data: unknown): NotificationRoute | null {
  const route = notificationRouteFor(data);
  if (!route) {
    console.warn('[push] notificação sem data; rota ignorada');
    return null;
  }
  if (!navigator) {
    console.warn(`[push] navegação indisponível; rota ${route.screen} descartada`);
    return route;
  }
  navigator(route);
  return route;
}

/**
 * Entrega o toque que abriu o app (cold start) uma única vez por processo.
 *
 * Deve ser chamado quando sessão e navegação estão prontas; antes disso a rota
 * não teria para onde ir. Sem resposta pendente não faz nada.
 */
export function routeColdStartNotification(): NotificationRoute | null {
  if (coldStartRouted) {
    return null;
  }
  coldStartRouted = true;
  captureColdStartResponse();
  const response = coldStartResponse;
  coldStartResponse = null;
  if (!response) {
    return null;
  }
  return routeResponse(response);
}

/**
 * Instala o handler de toque na notificação.
 *
 * O cold start é capturado antes do listener ao vivo e só é entregue depois,
 * com `routeColdStartNotification`, quando a navegação já existe.
 */
export function subscribeToNotificationResponses(): { remove: () => void } {
  captureColdStartResponse();
  const subscription = Notifications.addNotificationResponseReceivedListener((response) => {
    routeResponse(response);
  });
  return {
    remove: () => subscription.remove(),
  };
}
