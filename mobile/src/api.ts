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

export type SportFormat = {
  id: string;
  slug: string;
  name: string;
  team_size: number;
  total_participants: number;
  play_minutes: number;
  break_minutes: number;
  duration_minutes: number;
  version: number;
};

export type Sport = {
  id: string;
  slug: string;
  name: string;
  formats: SportFormat[];
};

export type Catalog = {
  sports: Sport[];
};

export type UserSport = {
  format_id: string;
  sport_slug: string;
  sport_name: string;
  format_name: string;
  level: string;
  court_preference: string;
};

export type Availability = {
  weekday: number;
  start_time: string;
  end_time: string;
  timezone: string;
};

export type Region = {
  source: string;
  cep: string | null;
  city: string | null;
  state: string | null;
  radius_km: number;
  updated_at: string;
};

export type Profile = {
  user_id: string;
  display_name: string | null;
  bio: string | null;
  sports: UserSport[];
  availability: Availability[];
  region: Region | null;
};

export type Venue = {
  id: string;
  name: string;
  kind: string;
  city: string;
  state: string;
  cep: string | null;
  address: string | null;
  lat: number;
  lng: number;
};

export type VenuePage = {
  items: Venue[];
  total: number;
  page: number;
  page_size: number;
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

export const profileApi = {
  catalog(): Promise<Catalog> {
    return call<Catalog>('/sports');
  },

  getProfile(accessToken: string): Promise<Profile> {
    return call<Profile>('/me/profile', {}, accessToken);
  },

  updateProfile(
    accessToken: string,
    displayName: string | null,
    bio: string | null,
  ): Promise<Profile> {
    return call<Profile>(
      '/me/profile',
      {
        method: 'PUT',
        body: JSON.stringify({ display_name: displayName, bio }),
      },
      accessToken,
    );
  },

  replaceSports(
    accessToken: string,
    sports: {
      format_id: string;
      level: string;
      court_preference: string;
    }[],
  ): Promise<Profile> {
    return call<Profile>(
      '/me/sports',
      { method: 'PUT', body: JSON.stringify({ sports }) },
      accessToken,
    );
  },

  replaceAvailability(
    accessToken: string,
    windows: {
      weekday: number;
      start_time: string;
      end_time: string;
      timezone?: string;
    }[],
  ): Promise<Profile> {
    return call<Profile>(
      '/me/availability',
      { method: 'PUT', body: JSON.stringify({ windows }) },
      accessToken,
    );
  },

  setRegionByCep(accessToken: string, cep: string, radiusKm: number): Promise<Profile> {
    return call<Profile>(
      '/me/region',
      {
        method: 'PUT',
        body: JSON.stringify({ cep, radius_km: radiusKm }),
      },
      accessToken,
    );
  },

  setRegionByLocation(
    accessToken: string,
    lat: number,
    lng: number,
    radiusKm: number,
  ): Promise<Profile> {
    return call<Profile>(
      '/me/location',
      {
        method: 'PUT',
        body: JSON.stringify({ lat, lng, radius_km: radiusKm }),
      },
      accessToken,
    );
  },

  discoverVenues(accessToken: string, page = 1, pageSize = 20): Promise<VenuePage> {
    return call<VenuePage>(`/discovery/venues?page=${page}&page_size=${pageSize}`, {}, accessToken);
  },
};
