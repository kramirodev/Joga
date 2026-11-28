import type {
  Availability,
  Badge,
  BookableVenueDetail,
  BookableVenuePage,
  Booking,
  Challenge,
  ChatMessage,
  Clan,
  ClanInvite,
  ClanJoinRequestRow,
  ClanJoinResult,
  ClanMember,
  ClanMessage,
  ClanRanking,
  ClanUpdate,
  CpfStatus,
  Device,
  EmailCredential,
  EmailVerification,
  Friend,
  FriendRequest,
  LobbyInvite,
  MatchSummary,
  Mission,
  ModerationAction,
  ModerationAppeal,
  ModerationReport,
  MyClanRequest,
  MyRating,
  Network,
  Notification,
  PassReceipt,
  PassSubscription,
  PassPlan,
  Passkey,
  PasskeyOptions,
  Passport,
  PlayerSearchResult,
  Presence,
  Profile,
  Progress,
  PublicPlayer,
  QueueEntry,
  QueueSelectionPayload,
  QueueStateResponse,
  Ranking,
  ResultView,
  Sport,
  Stats,
  Substitute,
  TermsAcceptance,
  TermsVersion,
  Tokens,
  Track,
  TrackLevel,
  VenuePage,
  VisualCatalog,
  VisualIdentity,
  VisualIdentityResponse,
  Wallet,
} from './types';

import { APP_BUILD, APP_VERSION, CLIENT_NAME, CLIENT_PLATFORM } from './version';
import { isExplicitSessionRevocation } from './refreshPolicy';
import { retryTokenAfterRefresh } from './tokenRetry';

// Configure pela variável de ambiente EXPO_PUBLIC_API_URL.
// Sem a variável, usa o backend local via `adb reverse tcp:8000 tcp:8000`.
const configuredApiUrl = process.env.EXPO_PUBLIC_API_URL?.trim();
export const API_BASE_URL = (configuredApiUrl || 'http://127.0.0.1:8000/api/v1').replace(
  /\/+$/,
  '',
);
export const API_ORIGIN = API_BASE_URL.replace(/\/api\/v1$/i, '');

export function apiAssetUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) {
    return path;
  }
  return `${API_ORIGIN}${path.startsWith('/') ? '' : '/'}${path}`;
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    readonly retryAfterSeconds?: number,
    readonly body?: unknown,
  ) {
    super(code);
  }
}

/** Diagnóstico legível para erros inesperados: status, código e corpo. */
export function describeApiError(error: unknown): string {
  if (error instanceof ApiError) {
    let detail = '';
    if (error.body !== undefined && error.body !== null) {
      try {
        detail = JSON.stringify(error.body);
      } catch {
        detail = String(error.body);
      }
      if (detail.length > 300) {
        detail = `${detail.slice(0, 300)}…`;
      }
    }
    return `HTTP ${error.status} · ${error.code}${detail ? ` · ${detail}` : ''}`;
  }
  return error instanceof Error ? error.message : String(error);
}

const REQUEST_TIMEOUT_MS = 15_000;

/**
 * Resultado explícito do refresh. `unavailable` cobre rede/timeout/5xx/429 e
 * 4xx sem revogação explícita; `retry` é a corrida transitória da ADR 0058.
 * Nenhum dos dois desloga nem acusa suspensão.
 */
export type RefreshResult =
  | { ok: true; token: string }
  | { ok: false; reason: 'suspended' | 'retry' | 'expired' | 'unavailable' };

let refreshHandler: (() => Promise<RefreshResult>) | null = null;
let refreshPromise: Promise<RefreshResult> | null = null;
let currentTokenProvider: (() => string | null) | null = null;
let suspensionHandler: (() => void) | null = null;
let sessionExpiredHandler: ((token?: string | null) => void) | null = null;
let updateRequiredHandler: (() => void) | null = null;

export function setRefreshHandler(handler: (() => Promise<RefreshResult>) | null) {
  refreshHandler = handler;
  if (!handler) {
    refreshPromise = null;
  }
}

/**
 * Token da sessão agora. `call()` consulta antes de renovar: se o token já
 * mudou, a resposta 401 veio de um token antigo e a chamada só precisa ser
 * repetida — renovar de novo revogaria o token recém-rotacionado.
 */
export function setCurrentTokenProvider(provider: (() => string | null) | null) {
  currentTokenProvider = provider;
}

export function setSuspensionHandler(handler: (() => void) | null) {
  suspensionHandler = handler;
}

/** Sessão inválida (401/403 explícito de token revogado; nunca transitório). */
export function setSessionExpiredHandler(handler: ((token?: string | null) => void) | null) {
  sessionExpiredHandler = handler;
}

export function setUpdateRequiredHandler(handler: (() => void) | null) {
  updateRequiredHandler = handler;
}

type Init = {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  token?: string | null;
  headers?: Record<string, string>;
  /** Não dispara o handler de sessão expirada (ex.: revalidar suspensão). */
  keepSession?: boolean;
};

async function call<T>(path: string, init: Init = {}, allowRefresh = true): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Client': CLIENT_NAME,
    'X-App-Version': APP_VERSION,
    'X-Build-Number': APP_BUILD,
    'X-Platform': CLIENT_PLATFORM,
    ...(init.token ? { Authorization: `Bearer ${init.token}` } : {}),
    ...(init.headers ?? {}),
  };
  let response: Response;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: init.method ?? 'GET',
      headers,
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiError(0, 'request_timeout');
    }
    throw new ApiError(0, 'network_unavailable');
  } finally {
    clearTimeout(timeout);
  }

  if (response.status === 426) {
    updateRequiredHandler?.();
  }

  let unauthorizedHandled = false;

  const retryWithToken = async (token: string): Promise<T> => {
    try {
      return await call<T>(path, { ...init, token }, false);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        // Só o corpo explícito do servidor pode acusar suspensão ou provar
        // que a sessão morreu. Rede/token recém-rotacionado e códigos
        // transitórios mantêm a sessão local.
        if (error.code === 'account_suspended') {
          suspensionHandler?.();
        } else if (!init.keepSession && isExplicitSessionRevocation(error.code)) {
          sessionExpiredHandler?.(token);
        }
      }
      throw error;
    }
  };

  if (response.status === 401 && init.token && allowRefresh) {
    const currentToken = currentTokenProvider?.() ?? null;
    if (currentToken && currentToken !== init.token) {
      // A sessão já tem um token mais novo: este 401 veio do token antigo.
      // Repetir com o atual evita outra rotação e a revogação em cascata.
      return retryWithToken(currentToken);
    }

    if (refreshHandler) {
      const refreshToken = init.token;
      if (!refreshPromise) {
        refreshPromise = refreshHandler().finally(() => {
          refreshPromise = null;
        });
      }
      const refreshed = await refreshPromise;
      if (refreshed.ok) {
        const latestToken = currentTokenProvider?.() ?? null;
        return retryWithToken(retryTokenAfterRefresh(refreshToken, latestToken, refreshed.token));
      }
      if (refreshed.reason === 'suspended') {
        suspensionHandler?.();
        unauthorizedHandled = true;
        throw new ApiError(401, 'account_suspended');
      }
      if (refreshed.reason === 'expired') {
        if (!init.keepSession) {
          sessionExpiredHandler?.(refreshToken);
        }
        unauthorizedHandled = true;
      }
      // `retry` persistente (ADR 0058) e `unavailable` (rede/timeout/5xx/429)
      // mantêm a sessão; o erro original chega à tela e a próxima chamada pode
      // recuperar. Nunca desloga nem acusa suspensão.
      if (refreshed.reason === 'retry' || refreshed.reason === 'unavailable') {
        unauthorizedHandled = true;
      }
    }
  }

  if (response.status === 204) {
    return undefined as T;
  }
  const text = await response.text();
  let body: unknown = null;
  if (text.length > 0) {
    try {
      body = JSON.parse(text);
    } catch {
      body = null;
    }
  }
  if (!response.ok) {
    const detail = (body as { detail?: unknown } | null)?.detail;
    let code = 'request_failed';
    if (typeof detail === 'string') {
      code = detail;
    } else if (detail && typeof detail === 'object') {
      const candidate = (detail as { code?: unknown }).code;
      if (typeof candidate === 'string') {
        code = candidate;
      } else if (Array.isArray(detail) && typeof detail[0]?.msg === 'string') {
        code = detail[0].msg;
      }
    }
    const error = new ApiError(
      response.status,
      code,
      retryAfterSeconds(response.headers.get('Retry-After')),
      body,
    );
    // Sem refresh disponível, um 401 com token só encerra a sessão quando o
    // servidor diz explicitamente que o token não vale mais. Nunca suspensão,
    // a menos que o corpo diga `account_suspended`.
    if (error.status === 401 && init.token && allowRefresh && !unauthorizedHandled) {
      if (error.code === 'account_suspended') {
        suspensionHandler?.();
      } else if (!init.keepSession && isExplicitSessionRevocation(error.code)) {
        sessionExpiredHandler?.(init.token);
      }
    }
    throw error;
  }
  return body as T;
}

function retryAfterSeconds(value: string | null): number | undefined {
  if (!value) {
    return undefined;
  }
  const seconds = Number(value.trim());
  if (Number.isFinite(seconds) && seconds >= 0) {
    return Math.ceil(seconds);
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return undefined;
  }
  return Math.max(0, Math.ceil((date.getTime() - Date.now()) / 1000));
}

function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const entries = Object.entries(params).filter(
    ([, value]) => value !== undefined && value !== null,
  );
  if (entries.length === 0) {
    return '';
  }
  return `?${entries
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
    .join('&')}`;
}

function key(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

/** Chave para cabeçalho `Idempotency-Key`; o backend limita a 120 caracteres. */
export function newIdempotencyKey(): string {
  return key();
}

export const api = {
  auth: {
    requestChallenge(phone: string, purpose: 'registration' | 'login') {
      return call<Challenge>('/auth/phone/challenges', {
        method: 'POST',
        body: { phone, purpose },
      });
    },
    verifyChallenge(challengeId: string, code: string) {
      return call<{ challenge_id: string; purpose: string }>(
        `/auth/phone/challenges/${encodeURIComponent(challengeId)}/verify`,
        { method: 'POST', body: { code } },
      );
    },
    register(challengeId: string, device?: { name: string; platform: string }) {
      return call<Tokens>('/auth/registration', {
        method: 'POST',
        body: { challenge_id: challengeId, ...(device ?? {}) },
      });
    },
    login(challengeId: string, device?: { name: string; platform: string }) {
      return call<Tokens>('/auth/login', {
        method: 'POST',
        body: { challenge_id: challengeId, ...(device ?? {}) },
      });
    },
    refresh(refreshToken: string) {
      return call<Tokens>('/auth/refresh', {
        method: 'POST',
        body: { refresh_token: refreshToken },
      });
    },
    me(token: string, keepSession = false) {
      return call<{ id: string; status: string }>('/auth/me', { token, keepSession });
    },
    logout(token: string) {
      return call<void>('/auth/logout', { method: 'POST', token });
    },
    logoutAll(token: string) {
      return call<void>('/auth/logout-all', { method: 'POST', token });
    },
    emailRequestCode(email: string, purpose: 'registration' | 'password_reset') {
      return call<Challenge>('/auth/email/code', {
        method: 'POST',
        body: { email, purpose },
      });
    },
    emailVerify(challengeId: string, code: string) {
      return call<EmailVerification>('/auth/email/verify', {
        method: 'POST',
        body: { challenge_id: challengeId, code },
      });
    },
    emailRegister(
      challengeId: string,
      email: string,
      password: string,
      displayName: string | null,
      device?: { name: string; platform: string },
    ) {
      return call<Tokens>('/auth/email/register', {
        method: 'POST',
        body: {
          challenge_id: challengeId,
          email,
          password,
          ...(displayName?.trim() ? { display_name: displayName.trim() } : {}),
          ...(device ? { device_name: device.name, platform: device.platform } : {}),
        },
      });
    },
    emailPasswordLogin(
      email: string,
      password: string,
      device?: { name: string; platform: string },
    ) {
      return call<Tokens>('/auth/email/login', {
        method: 'POST',
        body: {
          email,
          password,
          ...(device ? { device_name: device.name, platform: device.platform } : {}),
        },
      });
    },
    passwordReset(challengeId: string, email: string, newPassword: string) {
      return call<{ status: string }>('/auth/email/password/reset', {
        method: 'POST',
        body: {
          challenge_id: challengeId,
          email,
          new_password: newPassword,
        },
      });
    },
    changePassword(token: string, currentPassword: string, newPassword: string) {
      return call<{ status: string }>('/me/password', {
        method: 'POST',
        body: {
          current_password: currentPassword,
          new_password: newPassword,
        },
        token,
      });
    },
    emails(token: string) {
      return call<{ emails: EmailCredential[] }>('/auth/emails', { token });
    },
    emailChangeChallenge(token: string, newEmail: string) {
      return call<Challenge>('/me/account/email/challenges', {
        method: 'POST',
        body: { new_email: newEmail },
        token,
      });
    },
    emailChangeConfirm(token: string, newEmail: string, challengeId: string, code: string) {
      return call<EmailCredential>('/me/account/email', {
        method: 'PATCH',
        body: { new_email: newEmail, challenge_id: challengeId, code },
        token,
      });
    },
    phoneChangeChallenge(token: string, newPhone: string) {
      return call<Challenge>('/auth/phone-change/challenges', {
        method: 'POST',
        body: { new_phone: newPhone },
        token,
      });
    },
    phoneChangeConfirm(token: string, challengeId: string, code: string) {
      return call<void>('/auth/phone-change', {
        method: 'POST',
        body: { challenge_id: challengeId, code },
        token,
      });
    },
    passkeyRegistrationOptions(token: string) {
      return call<PasskeyOptions>('/auth/passkeys/registration/options', {
        method: 'POST',
        token,
      });
    },
    passkeyRegistrationVerify(
      token: string,
      challengeId: string,
      credential: Record<string, unknown>,
      name: string | null,
    ) {
      return call<{ credential_id: string; name: string | null }>(
        '/auth/passkeys/registration/verify',
        {
          method: 'POST',
          body: { challenge_id: challengeId, credential, name },
          token,
        },
      );
    },
    passkeyAuthenticationOptions() {
      return call<PasskeyOptions>('/auth/passkeys/authentication/options', { method: 'POST' });
    },
    passkeyAuthenticationVerify(
      challengeId: string,
      credential: Record<string, unknown>,
      device?: { name: string; platform: string },
    ) {
      return call<Tokens>('/auth/passkeys/authentication/verify', {
        method: 'POST',
        body: {
          challenge_id: challengeId,
          credential,
          ...(device ? { device_name: device.name, platform: device.platform } : {}),
        },
      });
    },
    passkeys(token: string) {
      return call<{ credentials: Passkey[] }>('/auth/passkeys', { token });
    },
    revokePasskey(token: string, credentialId: string) {
      return call<void>(`/auth/passkeys/${encodeURIComponent(credentialId)}`, {
        method: 'DELETE',
        token,
      });
    },
    devices(token: string) {
      return call<{ devices: Device[] }>('/auth/devices', { token });
    },
    revokeDevice(token: string, deviceId: string) {
      return call<void>(`/auth/devices/${encodeURIComponent(deviceId)}`, {
        method: 'DELETE',
        token,
      });
    },
  },

  profile: {
    catalog() {
      return call<{ sports: Sport[] }>('/sports');
    },
    me(token: string) {
      return call<Profile>('/me/profile', { token });
    },
    email(token: string) {
      return call<{ email: string | null }>('/me/email', { token });
    },
    updateEmail(token: string, email: string | null) {
      return call<{ email: string | null }>('/me/email', {
        method: 'PUT',
        body: { email },
        token,
      });
    },
    cpf(token: string) {
      return call<CpfStatus>('/me/cpf', { token });
    },
    updateCpf(token: string, cpf: string) {
      return call<CpfStatus>('/me/cpf', { method: 'PUT', body: { cpf }, token });
    },
    clearCpf(token: string) {
      return call<CpfStatus>('/me/cpf', { method: 'DELETE', token });
    },
    update(token: string, displayName: string | null, bio: string | null) {
      return call<Profile>('/me/profile', {
        method: 'PUT',
        body: { display_name: displayName, bio },
        token,
      });
    },
    /** Tema do cartão público; `null` volta ao padrão do app. */
    updateTheme(token: string, themeId: string | null) {
      return call<{ theme_id: string | null }>('/me/theme', {
        method: 'PUT',
        body: { theme_id: themeId },
        token,
      });
    },
    replaceSports(
      token: string,
      sports: { format_id: string; level: string; court_preference: string }[],
    ) {
      return call<Profile>('/me/sports', { method: 'PUT', body: { sports }, token });
    },
    replaceAvailability(token: string, windows: Availability[]) {
      return call<Profile>('/me/availability', {
        method: 'PUT',
        body: {
          windows: windows.map((item) => ({
            weekday: item.weekday,
            start_time: item.start_time,
            end_time: item.end_time,
            ...(item.timezone ? { timezone: item.timezone } : {}),
          })),
        },
        token,
      });
    },
    setRegionCep(token: string, cep: string, radiusKm: number) {
      return call<Profile>('/me/region', {
        method: 'PUT',
        body: { cep, radius_km: radiusKm },
        token,
      });
    },
    setRegionLocation(token: string, lat: number, lng: number, radiusKm: number) {
      return call<Profile>('/me/location', {
        method: 'PUT',
        body: { lat, lng, radius_km: radiusKm },
        token,
      });
    },
    venues(token: string, page = 1, pageSize = 20) {
      return call<VenuePage>(`/discovery/venues${qs({ page, page_size: pageSize })}`, { token });
    },
  },

  discovery: {
    bookableVenues(
      token: string,
      options: {
        page?: number;
        pageSize?: number;
        city?: string | null;
        formatId?: string | null;
        sportId?: string | null;
        covered?: boolean | null;
        maxDistanceKm?: number | null;
      } = {},
    ) {
      return call<BookableVenuePage>(
        `/discovery/bookable-venues${qs({
          page: options.page ?? 1,
          page_size: options.pageSize ?? 20,
          ...(options.city ? { city: options.city } : {}),
          ...(options.formatId ? { format_id: options.formatId } : {}),
          ...(options.sportId ? { sport_id: options.sportId } : {}),
          ...(options.covered !== undefined && options.covered !== null
            ? { covered: options.covered }
            : {}),
          ...(options.maxDistanceKm != null ? { max_distance_km: options.maxDistanceKm } : {}),
        })}`,
        { token },
      );
    },
    bookableVenue(token: string, venueId: string) {
      return call<BookableVenueDetail>(
        `/discovery/bookable-venues/${encodeURIComponent(venueId)}`,
        { token },
      );
    },
  },

  // Contrato 0057 (ADR 0057): a fila é substituída de forma atômica por
  // `PUT /matchmaking/queue`. `POST` continua existindo apenas para a retomada
  // single-entry do perfil de modalidades.
  queue: {
    replace(token: string, payload: QueueSelectionPayload) {
      return call<QueueStateResponse>('/matchmaking/queue', {
        method: 'PUT',
        body: payload,
        token,
      });
    },
    state(token: string) {
      return call<QueueStateResponse>('/matchmaking/queue', { token });
    },
    leave(token: string) {
      return call<void>('/matchmaking/queue', { method: 'DELETE', token });
    },
  },

  matchmaking: {
    enqueue(
      token: string,
      formatId: string,
      mode: 'casual' | 'ranked',
      courtPreference: 'PUBLIC_ONLY' | 'PRIVATE_ONLY' | 'ANY',
    ) {
      return call<QueueEntry>('/matchmaking/queue', {
        method: 'POST',
        body: { format_id: formatId, mode, court_preference: courtPreference },
        token,
      });
    },
  },

  matches: {
    list(token: string) {
      return call<{ matches: MatchSummary[] }>('/matches', { token });
    },
    get(token: string, matchId: string) {
      return call<MatchSummary>(`/matches/${encodeURIComponent(matchId)}`, { token });
    },
    confirm(token: string, matchId: string) {
      return call<MatchSummary>(`/matches/${encodeURIComponent(matchId)}/confirm`, {
        method: 'POST',
        token,
      });
    },
    decline(token: string, matchId: string) {
      return call<MatchSummary>(`/matches/${encodeURIComponent(matchId)}/decline`, {
        method: 'POST',
        token,
      });
    },
    checkIn(token: string, matchId: string) {
      return call<MatchSummary>(`/matches/${encodeURIComponent(matchId)}/check-in`, {
        method: 'POST',
        token,
      });
    },
  },

  ratings: {
    me(token: string, formatId: string) {
      return call<MyRating>(`/ratings/me${qs({ format_id: formatId })}`, { token });
    },
    ranking(token: string, formatId: string, limit = 50, offset = 0) {
      return call<Ranking>(`/rankings${qs({ format_id: formatId, limit, offset })}`, { token });
    },
  },

  progress: {
    get(token: string) {
      return call<Progress>('/me/progress', { token });
    },
    track(token: string) {
      return call<Track>('/me/progress/track', { token });
    },
    claim(token: string, level: number) {
      return call<TrackLevel>(`/me/progress/track/${level}/claim`, { method: 'POST', token });
    },
    badges(token: string) {
      return call<{ badges: Badge[] }>('/me/progress/badges', { token });
    },
    equipBadge(token: string, badgeId: string, slot: number) {
      return call<Badge>('/me/progress/badges/equip', {
        method: 'PUT',
        body: { badge_id: badgeId, slot },
        token,
      });
    },
    missions(token: string) {
      return call<{ week_start: string; missions: Mission[] }>('/me/progress/missions', { token });
    },
  },

  tickets: {
    wallet(token: string, limit = 20) {
      return call<Wallet>(`/me/tickets${qs({ limit })}`, { token });
    },
  },

  passes: {
    plans(token: string) {
      return call<{ plans: PassPlan[] }>('/me/pass/plans', { token });
    },
    get(token: string) {
      return call<{ subscription: PassSubscription | null }>('/me/pass', { token });
    },
    subscribe(token: string, planCode: string, idempotencyKey?: string, termsVersionId?: string) {
      return call<PassSubscription>('/me/pass/subscriptions', {
        method: 'POST',
        body: {
          plan_code: planCode,
          ...(termsVersionId ? { terms_version_id: termsVersionId } : {}),
        },
        token,
        headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined,
      });
    },
    subscription(token: string, subscriptionId: string) {
      return call<PassSubscription>(
        `/me/pass/subscriptions/${encodeURIComponent(subscriptionId)}`,
        { token },
      );
    },
    receipt(token: string, subscriptionId: string) {
      return call<PassReceipt>(
        `/me/pass/subscriptions/${encodeURIComponent(subscriptionId)}/receipt`,
        { token },
      );
    },
    sync(token: string, subscriptionId: string) {
      return call<PassSubscription>(
        `/me/pass/subscriptions/${encodeURIComponent(subscriptionId)}/sync`,
        { method: 'POST', token },
      );
    },
    cancel(token: string, subscriptionId: string) {
      return call<PassSubscription>(
        `/me/pass/subscriptions/${encodeURIComponent(subscriptionId)}`,
        { method: 'DELETE', token },
      );
    },
  },

  stats: {
    me(token: string, formatId?: string) {
      return call<Stats>(`/me/stats${qs({ format_id: formatId })}`, { token });
    },
    courts(token: string) {
      return call<{
        courts: {
          space_id: string;
          name: string;
          matches: number;
          wins: number;
          last_played_at: string;
        }[];
      }>('/me/stats/courts', { token });
    },
    passport(token: string) {
      return call<Passport>('/me/stats/passport', { token });
    },
    network(token: string) {
      return call<Network>('/me/network', { token });
    },
  },

  bookings: {
    create(
      token: string,
      input: {
        lobby_id: string;
        organization_venue_id: string;
        venue_space_id: string;
        starts_at: string;
        ends_at: string;
      },
    ) {
      return call<Booking>('/bookings', { method: 'POST', body: input, token });
    },
    list(token: string) {
      return call<{ bookings: Booking[] }>('/bookings', { token });
    },
    get(token: string, bookingId: string) {
      return call<Booking>(`/bookings/${encodeURIComponent(bookingId)}`, { token });
    },
    syncPayment(token: string, bookingId: string, paymentId: string) {
      return call<{ payment_id: string; status: string; provider_status: string | null }>(
        `/bookings/${encodeURIComponent(bookingId)}/payments/${encodeURIComponent(paymentId)}/sync`,
        { method: 'POST', token },
      );
    },
    preCheckIn(token: string, bookingId: string) {
      return call<Presence>(`/bookings/${encodeURIComponent(bookingId)}/pre-check-in`, {
        method: 'POST',
        token,
      });
    },
    confirmPresence(
      token: string,
      bookingId: string,
      input: {
        method: 'GPS' | 'VENUE';
        latitude?: number;
        longitude?: number;
        accuracy_m?: number;
      },
    ) {
      return call<Presence>(`/bookings/${encodeURIComponent(bookingId)}/presence`, {
        method: 'POST',
        body: input,
        token,
      });
    },
    presence(token: string, bookingId: string) {
      return call<{ participants: Presence[] }>(
        `/bookings/${encodeURIComponent(bookingId)}/presence`,
        { token },
      );
    },
    participantConfirmation(token: string, bookingId: string, decision: 'CONFIRM' | 'DECLINE') {
      return call<Booking>(`/bookings/${encodeURIComponent(bookingId)}/participant-confirmation`, {
        method: 'POST',
        body: { decision },
        token,
      });
    },
    settleWithTickets(token: string, bookingId: string) {
      return call<Booking>(`/bookings/${encodeURIComponent(bookingId)}/settle-with-tickets`, {
        method: 'POST',
        token,
      });
    },
    cancel(token: string, bookingId: string, reason: string) {
      return call<Booking>(`/bookings/${encodeURIComponent(bookingId)}/cancel`, {
        method: 'POST',
        body: { reason },
        token,
      });
    },
    substitutions(token: string, bookingId: string) {
      return call<{ substitutions: unknown[] }>(
        `/bookings/${encodeURIComponent(bookingId)}/substitutions`,
        { token },
      );
    },
  },

  legal: {
    currentTerms() {
      return call<{ terms: TermsVersion | null }>('/legal/terms/current');
    },
    acceptTerms(
      token: string,
      termsVersionId: string,
      context: 'signup' | 'credit_purchase' | 'pass_purchase' | 'booking_ceiling',
    ) {
      return call<TermsAcceptance>('/legal/terms/accept', {
        method: 'POST',
        body: { terms_version_id: termsVersionId, context },
        token,
      });
    },
  },

  notifications: {
    list(token: string, options: { unreadOnly?: boolean; limit?: number; offset?: number } = {}) {
      return call<{
        notifications: Notification[];
        unread_count: number;
        limit: number;
        offset: number;
      }>(
        `/me/notifications${qs({
          unread_only: options.unreadOnly ?? false,
          limit: options.limit ?? 30,
          offset: options.offset ?? 0,
        })}`,
        { token },
      );
    },
    unreadCount(token: string) {
      return call<{ unread_count: number }>('/me/notifications/unread-count', { token });
    },
    markRead(token: string, notificationId: string) {
      return call<Notification>(`/me/notifications/${encodeURIComponent(notificationId)}/read`, {
        method: 'POST',
        token,
      });
    },
    markAllRead(token: string) {
      return call<{ updated: number }>('/me/notifications/read-all', {
        method: 'POST',
        token,
      });
    },
  },

  moderation: {
    createReport(
      token: string,
      input: {
        target_user_id: string;
        lobby_id: string;
        category: string;
        description: string;
        message_ids?: string[];
      },
    ) {
      return call<ModerationReport>('/moderation/reports', {
        method: 'POST',
        body: input,
        token,
      });
    },
    listMyReports(token: string) {
      return call<{ reports: ModerationReport[] }>('/moderation/reports/me', { token });
    },
    listMyActions(token: string) {
      return call<{ actions: ModerationAction[] }>('/moderation/actions/me', { token });
    },
    listMyAppeals(token: string) {
      return call<{ appeals: ModerationAppeal[] }>('/moderation/appeals/me', { token });
    },
    appeal(token: string, actionId: string, reason: string) {
      return call<ModerationAppeal>(`/moderation/actions/${encodeURIComponent(actionId)}/appeal`, {
        method: 'POST',
        body: { reason },
        token,
      });
    },
  },

  substitutions: {
    joinQueue(token: string, lobbyId: string) {
      return call<Substitute>(`/lobbies/${encodeURIComponent(lobbyId)}/substitutes`, {
        method: 'POST',
        token,
      });
    },
    leaveQueue(token: string, lobbyId: string) {
      return call<void>(`/lobbies/${encodeURIComponent(lobbyId)}/substitutes`, {
        method: 'DELETE',
        token,
      });
    },
    listQueue(token: string, lobbyId: string) {
      return call<{ substitutes: Substitute[]; count: number }>(
        `/lobbies/${encodeURIComponent(lobbyId)}/substitutes`,
        { token },
      );
    },
    cancelParticipant(token: string, bookingId: string) {
      return call<unknown>(`/bookings/${encodeURIComponent(bookingId)}/participant-cancellations`, {
        method: 'POST',
        token,
      });
    },
    noShow(token: string, bookingId: string, userId: string, reason?: string) {
      return call<unknown>(
        `/bookings/${encodeURIComponent(bookingId)}/participants/${encodeURIComponent(userId)}/no-show`,
        { method: 'POST', body: { reason: reason ?? null }, token },
      );
    },
    assign(token: string, bookingId: string, substitutionId: string, substituteUserId: string) {
      return call<unknown>(
        `/bookings/${encodeURIComponent(bookingId)}/substitutions/${encodeURIComponent(substitutionId)}/assign`,
        { method: 'POST', body: { substitute_user_id: substituteUserId }, token },
      );
    },
    accept(token: string, bookingId: string, substitutionId: string) {
      return call<unknown>(
        `/bookings/${encodeURIComponent(bookingId)}/substitutions/${encodeURIComponent(substitutionId)}/accept`,
        { method: 'POST', token },
      );
    },
    decline(token: string, bookingId: string, substitutionId: string) {
      return call<unknown>(
        `/bookings/${encodeURIComponent(bookingId)}/substitutions/${encodeURIComponent(substitutionId)}/decline`,
        { method: 'POST', token },
      );
    },
  },

  results: {
    get(token: string, matchId: string) {
      return call<ResultView>(`/matches/${encodeURIComponent(matchId)}/result`, { token });
    },
    reports(token: string, matchId: string, round?: number) {
      return call<unknown>(
        `/matches/${encodeURIComponent(matchId)}/result-reports${qs({ round })}`,
        {
          token,
        },
      );
    },
    submit(token: string, matchId: string, round: number, outcome: 'TEAM_1' | 'TEAM_2' | 'DRAW') {
      return call<unknown>(`/matches/${encodeURIComponent(matchId)}/result-reports`, {
        method: 'POST',
        body: { round, outcome },
        token,
        headers: { 'Idempotency-Key': key() },
      });
    },
    confirm(token: string, matchId: string, round: number, outcome: 'TEAM_1' | 'TEAM_2' | 'DRAW') {
      return call<unknown>(`/matches/${encodeURIComponent(matchId)}/result-confirmations`, {
        method: 'POST',
        body: { round, outcome },
        token,
        headers: { 'Idempotency-Key': key() },
      });
    },
    submitEvidence(token: string, matchId: string, disputeId: string, text: string) {
      return call<unknown>(
        `/matches/${encodeURIComponent(matchId)}/disputes/${encodeURIComponent(disputeId)}/evidence`,
        {
          method: 'POST',
          body: { text },
          token,
          headers: { 'Idempotency-Key': key() },
        },
      );
    },
    myEvidence(token: string, matchId: string, disputeId: string) {
      return call<{ evidence_id: string; text: string; char_count: number; created_at: string }>(
        `/matches/${encodeURIComponent(matchId)}/disputes/${encodeURIComponent(disputeId)}/evidence/me`,
        { token },
      );
    },
  },

  chat: {
    list(token: string, lobbyId: string, before?: string) {
      return call<{ messages: ChatMessage[] }>(
        `/lobbies/${encodeURIComponent(lobbyId)}/messages${qs({ before })}`,
        { token },
      );
    },
    send(token: string, lobbyId: string, body: string) {
      return call<ChatMessage>(`/lobbies/${encodeURIComponent(lobbyId)}/messages`, {
        method: 'POST',
        body: { body },
        token,
        headers: { 'Idempotency-Key': key() },
      });
    },
  },

  users: {
    /** Busca pública por nome parcial, tag exata ou `NOME#TAG`. */
    search(token: string, q: string, limit = 20) {
      return call<{ results: PlayerSearchResult[] }>(`/users/search${qs({ q, limit })}`, {
        token,
      });
    },
    /** Perfil público mínimo; conta inexistente, inativa ou bloqueada é 404. */
    get(token: string, userId: string) {
      return call<PublicPlayer>(`/users/${encodeURIComponent(userId)}`, { token });
    },
  },

  social: {
    friends(token: string) {
      return call<{ friends: Friend[] }>('/friends', { token });
    },
    friendRequests(
      token: string,
      direction: 'incoming' | 'outgoing' = 'incoming',
      status: 'pending' | 'history' = 'pending',
    ) {
      return call<{ requests: FriendRequest[] }>(`/friends/requests${qs({ direction, status })}`, {
        token,
      });
    },
    requestFriend(token: string, userId: string) {
      return call<{ id: string; status: string }>('/friends/requests', {
        method: 'POST',
        body: { user_id: userId },
        token,
      });
    },
    acceptFriend(token: string, requestId: string) {
      return call<{ id: string; status: string }>(
        `/friends/requests/${encodeURIComponent(requestId)}/accept`,
        { method: 'POST', token },
      );
    },
    declineFriendRequest(token: string, requestId: string) {
      return call<{ id: string; status: string }>(
        `/friends/requests/${encodeURIComponent(requestId)}/decline`,
        { method: 'POST', token },
      );
    },
    cancelFriendRequest(token: string, requestId: string) {
      return call<{ id: string; status: string }>(
        `/friends/requests/${encodeURIComponent(requestId)}`,
        { method: 'DELETE', token },
      );
    },
    removeFriend(token: string, userId: string) {
      return call<void>(`/friends/${encodeURIComponent(userId)}`, { method: 'DELETE', token });
    },
    blocks(token: string) {
      return call<{ blocks: Friend[] }>('/blocks', { token });
    },
    blockUser(token: string, userId: string) {
      return call<{ status: string }>('/blocks', {
        method: 'POST',
        body: { user_id: userId },
        token,
      });
    },
    unblockUser(token: string, userId: string) {
      return call<void>(`/blocks/${encodeURIComponent(userId)}`, { method: 'DELETE', token });
    },
    invites(token: string) {
      return call<{ invites: LobbyInvite[] }>('/lobby-invites', { token });
    },
    inviteToLobby(token: string, lobbyId: string, userId: string) {
      return call<LobbyInvite>(`/lobbies/${encodeURIComponent(lobbyId)}/invites`, {
        method: 'POST',
        body: { user_id: userId },
        token,
      });
    },
    acceptInvite(token: string, inviteId: string) {
      return call<LobbyInvite>(`/lobby-invites/${encodeURIComponent(inviteId)}/accept`, {
        method: 'POST',
        token,
      });
    },
    declineInvite(token: string, inviteId: string) {
      return call<LobbyInvite>(`/lobby-invites/${encodeURIComponent(inviteId)}/decline`, {
        method: 'POST',
        token,
      });
    },
  },

  clans: {
    create(token: string, name: string, tag: string, description: string | null) {
      return call<Clan>('/clans', {
        method: 'POST',
        body: { name, tag, description },
        token,
      });
    },
    list(
      token: string,
      filters: { q?: string; open?: boolean; has_slots?: boolean; limit?: number } = {},
    ) {
      return call<{ clans: Clan[] }>(
        `/clans${qs({
          q: filters.q,
          open: filters.open,
          has_slots: filters.has_slots,
          limit: filters.limit ?? 20,
        })}`,
        { token },
      );
    },
    /** Só nome, descrição e política: a tag é imutável e não existe no tipo. */
    update(token: string, clanId: string, patch: ClanUpdate) {
      return call<Clan>(`/clans/${encodeURIComponent(clanId)}`, {
        method: 'PATCH',
        body: patch,
        token,
      });
    },
    ranking(token: string, formatId?: string, limit = 20) {
      return call<ClanRanking>(`/clans/ranking${qs({ format_id: formatId, limit })}`, { token });
    },
    mine(token: string) {
      return call<Clan | null>('/me/clan', { token });
    },
    myRequests(token: string, status: 'pending' | 'history' = 'pending') {
      return call<{ requests: MyClanRequest[] }>(`/me/clan-requests${qs({ status })}`, { token });
    },
    get(token: string, clanId: string) {
      return call<Clan>(`/clans/${encodeURIComponent(clanId)}`, { token });
    },
    join(token: string, clanId: string, message?: string) {
      return call<ClanJoinResult>(`/clans/${encodeURIComponent(clanId)}/join`, {
        method: 'POST',
        body: { message: message ?? null },
        token,
      });
    },
    members(token: string, clanId: string) {
      return call<{ members: ClanMember[] }>(`/clans/${encodeURIComponent(clanId)}/members`, {
        token,
      });
    },
    leave(token: string, clanId: string) {
      return call<void>(`/clans/${encodeURIComponent(clanId)}/leave`, {
        method: 'POST',
        token,
      });
    },
    messages(token: string, clanId: string, limit = 50) {
      return call<{ messages: ClanMessage[] }>(
        `/clans/${encodeURIComponent(clanId)}/messages${qs({ limit })}`,
        { token },
      );
    },
    sendMessage(token: string, clanId: string, body: string) {
      return call<ClanMessage>(`/clans/${encodeURIComponent(clanId)}/messages`, {
        method: 'POST',
        body: { body },
        token,
      });
    },
    reportMessage(token: string, clanId: string, messageId: string, reason: string) {
      return call<unknown>(
        `/clans/${encodeURIComponent(clanId)}/messages/${encodeURIComponent(messageId)}/report`,
        { method: 'POST', body: { reason }, token },
      );
    },
    removeMember(token: string, clanId: string, userId: string) {
      return call<ClanMember>(
        `/clans/${encodeURIComponent(clanId)}/members/${encodeURIComponent(userId)}`,
        { method: 'DELETE', token },
      );
    },
    setRole(token: string, clanId: string, userId: string, role: 'admin' | 'member') {
      return call<ClanMember>(
        `/clans/${encodeURIComponent(clanId)}/members/${encodeURIComponent(userId)}/role`,
        { method: 'POST', body: { role }, token },
      );
    },
    transfer(token: string, clanId: string, userId: string) {
      return call<ClanMember>(`/clans/${encodeURIComponent(clanId)}/transfer`, {
        method: 'POST',
        body: { user_id: userId },
        token,
      });
    },
    requests(token: string, clanId: string, status: 'pending' | 'history' = 'pending') {
      return call<{ requests: ClanJoinRequestRow[] }>(
        `/clans/${encodeURIComponent(clanId)}/requests${qs({ status })}`,
        { token },
      );
    },
    decideRequest(
      token: string,
      clanId: string,
      requestId: string,
      approve: boolean,
      note?: string,
    ) {
      return call<ClanJoinRequestRow>(
        `/clans/${encodeURIComponent(clanId)}/requests/${encodeURIComponent(requestId)}/decide`,
        { method: 'POST', body: { approve, note: note?.trim() || null }, token },
      );
    },
    cancelRequest(token: string, clanId: string, requestId: string) {
      return call<ClanJoinRequestRow>(
        `/clans/${encodeURIComponent(clanId)}/requests/${encodeURIComponent(requestId)}`,
        { method: 'DELETE', token },
      );
    },
    invites(token: string, clanId: string, status: 'pending' | 'history' = 'pending') {
      return call<{ invites: ClanInvite[] }>(
        `/clans/${encodeURIComponent(clanId)}/invites${qs({ status })}`,
        { token },
      );
    },
    invite(token: string, clanId: string, userId: string) {
      return call<ClanInvite>(`/clans/${encodeURIComponent(clanId)}/invites`, {
        method: 'POST',
        body: { user_id: userId },
        token,
      });
    },
    receivedInvites(token: string) {
      return call<{ invites: ClanInvite[] }>('/me/clan-invites', { token });
    },
    acceptInvite(token: string, inviteId: string) {
      return call<Clan>(`/clans/invites/${encodeURIComponent(inviteId)}/accept`, {
        method: 'POST',
        token,
      });
    },
    declineInvite(token: string, inviteId: string) {
      return call<ClanInvite>(`/clans/invites/${encodeURIComponent(inviteId)}/decline`, {
        method: 'POST',
        token,
      });
    },
    cancelInvite(token: string, clanId: string, inviteId: string) {
      return call<ClanInvite>(
        `/clans/${encodeURIComponent(clanId)}/invites/${encodeURIComponent(inviteId)}`,
        { method: 'DELETE', token },
      );
    },
  },

  visual: {
    catalog() {
      return call<VisualCatalog>('/catalog/visual');
    },
    me(token: string) {
      return call<VisualIdentityResponse>('/me/visual', { token });
    },
    update(token: string, identity: Omit<VisualIdentity, 'catalog_version'>) {
      return call<VisualIdentityResponse>('/me/visual', {
        method: 'PUT',
        body: identity,
        token,
      });
    },
  },

  health(token?: string) {
    return call<{ status: string }>('/ready', { token });
  },
};
