import * as SecureStore from 'expo-secure-store';

import { api, ApiError } from './api/client';
import { sessionRecoveryDecision, shouldRetryRefresh } from './api/refreshPolicy';
import { createSingleFlight } from './api/singleFlight';
import type { Tokens } from './api/types';

const ACCESS_KEY = 'joga.access_token';
const REFRESH_KEY = 'joga.refresh_token';
const USER_KEY = 'joga.user';
const EXPIRES_KEY = 'joga.access_expires_at';

export type Session = {
  accessToken: string;
  refreshToken: string;
  userId: string;
  userStatus: string;
  accessExpiresAt: string;
};

function toSession(tokens: Tokens): Session {
  return {
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
    userId: tokens.user.id,
    userStatus: tokens.user.status,
    accessExpiresAt: tokens.access_expires_at,
  };
}

export async function saveSession(tokens: Tokens): Promise<Session> {
  const session = toSession(tokens);
  await Promise.all([
    SecureStore.setItemAsync(ACCESS_KEY, session.accessToken),
    SecureStore.setItemAsync(REFRESH_KEY, session.refreshToken),
    SecureStore.setItemAsync(USER_KEY, JSON.stringify(tokens.user)),
    SecureStore.setItemAsync(EXPIRES_KEY, session.accessExpiresAt),
  ]);
  return session;
}

/** Lê o par gravado, sem disparar refresh nem apagar nada. */
async function readStoredSession(): Promise<Session | null> {
  const [accessToken, refreshToken, rawUser, expiresAt] = await Promise.all([
    SecureStore.getItemAsync(ACCESS_KEY),
    SecureStore.getItemAsync(REFRESH_KEY),
    SecureStore.getItemAsync(USER_KEY),
    SecureStore.getItemAsync(EXPIRES_KEY),
  ]);
  if (!accessToken || !refreshToken || !rawUser) {
    return null;
  }
  let user: { id: string; status: string };
  try {
    user = JSON.parse(rawUser) as { id: string; status: string };
  } catch {
    await clearSession();
    return null;
  }
  return {
    accessToken,
    refreshToken,
    userId: user.id,
    userStatus: user.status,
    accessExpiresAt: expiresAt ?? '',
  };
}

export async function loadSession(): Promise<Session | null> {
  const session = await readStoredSession();
  if (!session) {
    return null;
  }
  if (session.accessExpiresAt) {
    const expiry = new Date(session.accessExpiresAt).getTime();
    if (Number.isFinite(expiry) && expiry < Date.now() + 30_000) {
      try {
        return await refreshSession(session);
      } catch (error) {
        const apiError = error instanceof ApiError ? error : null;
        // Rede/timeout/5xx/429, `refresh_retry_required` e suspensão mantêm a
        // sessão local: a próxima chamada pode recuperar. Só a revogação
        // explícita do refresh apaga os tokens.
        const decision = sessionRecoveryDecision(apiError?.status ?? 0, apiError?.code);
        if (decision === 'clear') {
          await clearSession();
          return null;
        }
        return session;
      }
    }
  }
  return session;
}

const refreshGate = createSingleFlight<string, Session>();

/**
 * Último par rotacionado, por refresh token de origem. Protege contra um
 * chamador atrasado que ainda esteja com o token antigo depois do término do
 * single-flight: o backend revoga a família inteira ao detectar reuso.
 *
 * Guarda as duas origens possíveis de uma rotação com retry: o token que o
 * chamador tinha e o par mais novo lido do armazenamento seguro.
 */
let lastRotation: { used: string[]; session: Session } | null = null;

function rotatedFor(refreshToken: string): Session | null {
  return lastRotation?.used.includes(refreshToken) ? lastRotation.session : null;
}

function rememberRotation(used: string[], session: Session): Session {
  lastRotation = { used, session };
  return session;
}

async function rotate(refreshToken: string): Promise<Session> {
  const refreshed = await api.auth.refresh(refreshToken);
  return saveSession(refreshed);
}

function isRetryRequired(error: unknown): boolean {
  return error instanceof ApiError && shouldRetryRefresh(error.status, error.code);
}

/**
 * Única porta de entrada do refresh de sessão.
 *
 * - serializa por refresh token: duas chamadas concorrentes aguardam a mesma
 *   promessa e fazem **um** `POST /auth/refresh`;
 * - grava o par rotacionado antes de liberar os chamadores, para que um
 *   restart nunca reuse o token antigo (o backend revoga a família inteira ao
 *   detectar reuso);
 * - em `refresh_retry_required` (corrida transitória da ADR 0058), relê o
 *   armazenamento seguro e repete **uma vez** com o par mais novo; se
 *   persistir, o erro sobe e quem chama mantém a sessão;
 * - devolve a rotação já feita para um chamador atrasado com o token antigo;
 * - não limpa sessão aqui: quem chama classifica 401/rede/suspensão.
 */
export function refreshSession(session: Session): Promise<Session> {
  const cached = rotatedFor(session.refreshToken);
  if (cached) {
    return Promise.resolve(cached);
  }
  return refreshGate.run(session.refreshToken, async () => {
    const alreadyRotated = rotatedFor(session.refreshToken);
    if (alreadyRotated) {
      return alreadyRotated;
    }
    const used = [session.refreshToken];
    let token = session.refreshToken;
    try {
      return rememberRotation(used, await rotate(token));
    } catch (error) {
      if (!isRetryRequired(error)) {
        throw error;
      }
    }
    // A chamada vencedora da corrida pode ter gravado um par mais novo.
    const stored = await readStoredSession();
    if (stored && stored.refreshToken !== token) {
      token = stored.refreshToken;
      used.push(token);
    }
    return rememberRotation(used, await rotate(token));
  });
}

export function refreshStoredSession(session: Session): Promise<Session> {
  return refreshSession(session);
}

export async function clearSession(): Promise<void> {
  lastRotation = null;
  await Promise.all([
    SecureStore.deleteItemAsync(ACCESS_KEY),
    SecureStore.deleteItemAsync(REFRESH_KEY),
    SecureStore.deleteItemAsync(USER_KEY),
    SecureStore.deleteItemAsync(EXPIRES_KEY),
  ]);
}
