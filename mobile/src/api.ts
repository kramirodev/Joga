export const API_BASE_URL = 'http://127.0.0.1:8000/api/v1';

export type Challenge = {
  challenge_id: string;
  expires_at: string;
  resend_after_seconds: number;
};

export type UserSummary = {
  id: string;
  status: string;
};

export type Tokens = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  access_expires_at: string;
  refresh_expires_at: string;
  user: UserSummary;
};

export type PasskeyOptions = {
  challenge_id: string;
  public_key: Record<string, unknown>;
  expires_at: string;
};

export type PasskeySummary = {
  credential_id: string;
  name: string | null;
  created_at: string;
  last_used_at: string | null;
};

export type DeviceInfo = {
  name: string;
  platform: 'android' | 'ios' | 'web' | 'unknown';
};

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
  ) {
    super(code);
  }
}

async function call<T>(path: string, init: RequestInit = {}, accessToken?: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...(init.headers ?? {}),
    },
  });

  if (response.status === 204) {
    return undefined as unknown as T;
  }

  const text = await response.text();
  const body = text.length > 0 ? JSON.parse(text) : null;

  if (!response.ok) {
    const detail = body?.detail;
    const code =
      typeof detail?.code === 'string'
        ? detail.code
        : Array.isArray(detail) && typeof detail[0]?.msg === 'string'
          ? detail[0].msg
          : 'request_failed';
    throw new ApiError(response.status, code);
  }

  return body as T;
}

export const identityApi = {
  requestChallenge(phone: string, purpose: 'registration' | 'login'): Promise<Challenge> {
    return call<Challenge>('/auth/phone/challenges', {
      method: 'POST',
      body: JSON.stringify({ phone, purpose }),
    });
  },

  verifyChallenge(challengeId: string, code: string) {
    return call<{ challenge_id: string; purpose: string }>(
      `/auth/phone/challenges/${challengeId}/verify`,
      { method: 'POST', body: JSON.stringify({ code }) },
    );
  },

  register(challengeId: string, device?: DeviceInfo): Promise<Tokens> {
    return call<Tokens>('/auth/registration', {
      method: 'POST',
      body: JSON.stringify({
        challenge_id: challengeId,
        ...(device ? { device_name: device.name, platform: device.platform } : {}),
      }),
    });
  },

  login(challengeId: string, device?: DeviceInfo): Promise<Tokens> {
    return call<Tokens>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({
        challenge_id: challengeId,
        ...(device ? { device_name: device.name, platform: device.platform } : {}),
      }),
    });
  },

  refresh(refreshToken: string): Promise<Tokens> {
    return call<Tokens>('/auth/refresh', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  },

  me(accessToken: string): Promise<UserSummary> {
    return call<UserSummary>('/auth/me', {}, accessToken);
  },

  logout(accessToken: string): Promise<void> {
    return call<void>('/auth/logout', { method: 'POST' }, accessToken);
  },

  passkeyRegistrationOptions(accessToken: string): Promise<PasskeyOptions> {
    return call<PasskeyOptions>(
      '/auth/passkeys/registration/options',
      { method: 'POST' },
      accessToken,
    );
  },

  passkeyRegistrationVerify(accessToken: string, challengeId: string, credential: unknown) {
    return call<{ credential_id: string; name: string | null }>(
      '/auth/passkeys/registration/verify',
      {
        method: 'POST',
        body: JSON.stringify({
          challenge_id: challengeId,
          credential,
          name: 'Android',
        }),
      },
      accessToken,
    );
  },

  passkeyAuthenticationOptions(): Promise<PasskeyOptions> {
    return call<PasskeyOptions>('/auth/passkeys/authentication/options', {
      method: 'POST',
    });
  },

  passkeyAuthenticationVerify(
    challengeId: string,
    credential: unknown,
    device?: DeviceInfo,
  ): Promise<Tokens> {
    return call<Tokens>('/auth/passkeys/authentication/verify', {
      method: 'POST',
      body: JSON.stringify({
        challenge_id: challengeId,
        credential,
        ...(device ? { device_name: device.name, platform: device.platform } : {}),
      }),
    });
  },

  passkeys(accessToken: string): Promise<{ credentials: PasskeySummary[] }> {
    return call<{ credentials: PasskeySummary[] }>('/auth/passkeys', {}, accessToken);
  },

  phoneChangeChallenge(accessToken: string, newPhone: string): Promise<Challenge> {
    return call<Challenge>(
      '/auth/phone-change/challenges',
      { method: 'POST', body: JSON.stringify({ new_phone: newPhone }) },
      accessToken,
    );
  },

  phoneChangeConfirm(accessToken: string, challengeId: string, code: string): Promise<void> {
    return call<void>(
      '/auth/phone-change',
      {
        method: 'POST',
        body: JSON.stringify({ challenge_id: challengeId, code }),
      },
      accessToken,
    );
  },
};
