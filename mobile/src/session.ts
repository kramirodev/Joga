import * as SecureStore from 'expo-secure-store';

import { api, ApiError } from './api/client';
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
        const refreshed = await api.auth.refresh(refreshToken);
        return saveSession(refreshed);
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

export async function refreshStoredSession(session: Session): Promise<Session> {
  const refreshed = await api.auth.refresh(session.refreshToken);
  return saveSession(refreshed);
}

export async function clearSession(): Promise<void> {
  await Promise.all([
    SecureStore.deleteItemAsync(ACCESS_KEY),
    SecureStore.deleteItemAsync(REFRESH_KEY),
    SecureStore.deleteItemAsync(USER_KEY),
    SecureStore.deleteItemAsync(EXPIRES_KEY),
  ]);
}
