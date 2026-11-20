import * as SecureStore from 'expo-secure-store';

import { api, ApiError } from './api/client';
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

export async function loadSession(): Promise<Session | null> {
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
  const session: Session = {
    accessToken,
    refreshToken,
    userId: user.id,
    userStatus: user.status,
    accessExpiresAt: expiresAt ?? '',
  };
  if (expiresAt) {
    const expiry = new Date(expiresAt).getTime();
    if (Number.isFinite(expiry) && expiry < Date.now() + 30_000) {
      try {
        return await refreshSession(session);
      } catch (error) {
        if (error instanceof ApiError && error.status === 0) {
          return session;
        }
        if (error instanceof ApiError && error.code === 'account_suspended') {
          // A conta segue suspensa; preserva a sessão para a tela de suspensão.
          return session;
        }
        await clearSession();
        return null;
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
 */
let lastRotation: { used: string; session: Session } | null = null;

/**
 * Única porta de entrada do refresh de sessão.
 *
 * - serializa por refresh token: duas chamadas concorrentes aguardam a mesma
 *   promessa e fazem **um** `POST /auth/refresh`;
 * - grava o par rotacionado antes de liberar os chamadores, para que um
 *   restart nunca reuse o token antigo (o backend revoga a família inteira ao
 *   detectar reuso);
 * - devolve a rotação já feita para um chamador atrasado com o token antigo;
 * - não limpa sessão aqui: quem chama classifica 401/rede/suspensão.
 */
export function refreshSession(session: Session): Promise<Session> {
  if (lastRotation && lastRotation.used === session.refreshToken) {
    return Promise.resolve(lastRotation.session);
  }
  return refreshGate.run(session.refreshToken, async () => {
    if (lastRotation && lastRotation.used === session.refreshToken) {
      return lastRotation.session;
    }
    const refreshed = await api.auth.refresh(session.refreshToken);
    const saved = await saveSession(refreshed);
    lastRotation = { used: session.refreshToken, session: saved };
    return saved;
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
