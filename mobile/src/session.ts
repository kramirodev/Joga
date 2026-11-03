import * as SecureStore from 'expo-secure-store';

import type { Tokens } from './api';

const ACCESS_KEY = 'joga.access_token';
const REFRESH_KEY = 'joga.refresh_token';
const USER_KEY = 'joga.user';

export type StoredSession = {
  accessToken: string;
  refreshToken: string;
  userId: string;
  userStatus: string;
};

export async function saveSession(tokens: Tokens): Promise<StoredSession> {
  const session: StoredSession = {
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
    userId: tokens.user.id,
    userStatus: tokens.user.status,
  };

  await Promise.all([
    SecureStore.setItemAsync(ACCESS_KEY, session.accessToken),
    SecureStore.setItemAsync(REFRESH_KEY, session.refreshToken),
    SecureStore.setItemAsync(USER_KEY, JSON.stringify(tokens.user)),
  ]);

  return session;
}

export async function loadSession(): Promise<StoredSession | null> {
  const [accessToken, refreshToken, rawUser] = await Promise.all([
    SecureStore.getItemAsync(ACCESS_KEY),
    SecureStore.getItemAsync(REFRESH_KEY),
    SecureStore.getItemAsync(USER_KEY),
  ]);

  if (!accessToken || !refreshToken || !rawUser) {
    return null;
  }

  try {
    const user = JSON.parse(rawUser) as { id: string; status: string };
    return {
      accessToken,
      refreshToken,
      userId: user.id,
      userStatus: user.status,
    };
  } catch {
    await clearSession();
    return null;
  }
}

export async function clearSession(): Promise<void> {
  await Promise.all([
    SecureStore.deleteItemAsync(ACCESS_KEY),
    SecureStore.deleteItemAsync(REFRESH_KEY),
    SecureStore.deleteItemAsync(USER_KEY),
  ]);
}
