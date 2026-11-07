import type {
  AuditListResponse,
  ChallengeResponse,
  Member,
  MemberListResponse,
  Organization,
  OrganizationListResponse,
  Role,
  SportCatalogResponse,
  Venue,
  VenueAvailability,
  VenueAvailabilityListResponse,
  VenueBlackout,
  VenueBlackoutListResponse,
  VenueListResponse,
  VenuePhoto,
  VenuePhotoListResponse,
  VenueSpace,
  VenueSpaceListResponse,
  VerifyResponse,
  WebSessionPayload,
} from "../types";

const API_BASE = "/api/v1";
const CSRF_COOKIE = "joga_web_csrf";

let accessToken: string | null = null;
let csrfToken: string | null = null;
let refreshInFlight: Promise<WebSessionPayload | null> | null = null;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string | null;

  constructor(status: number, code: string, message?: string, requestId?: string | null) {
    super(message ?? code);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId ?? null;
  }
}

export function setAuthTokens(tokens: { accessToken: string; csrfToken: string }): void {
  accessToken = tokens.accessToken;
  csrfToken = tokens.csrfToken;
}

export function clearAuthTokens(): void {
  accessToken = null;
  csrfToken = null;
}

function readCookie(name: string): string | null {
  const prefix = `${encodeURIComponent(name)}=`;
  for (const part of document.cookie.split(";")) {
    const item = part.trim();
    if (item.startsWith(prefix)) {
      return decodeURIComponent(item.slice(prefix.length));
    }
  }
  return null;
}

function currentCsrf(): string | null {
  return csrfToken ?? readCookie(CSRF_COOKIE);
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.status === 204) {
    return undefined as T;
  }

  const requestId = response.headers.get("x-request-id");
  const text = await response.text();
  if (!response.ok) {
    let code = "request_failed";
    let message = `Falha na requisição (${response.status}).`;
    if (text) {
      try {
        const body = JSON.parse(text) as { detail?: unknown };
        if (typeof body.detail === "object" && body.detail !== null) {
          const detail = body.detail as { code?: unknown };
          if (typeof detail.code === "string") code = detail.code;
        } else if (typeof body.detail === "string") {
          message = body.detail;
        }
      } catch {
        // Resposta não JSON: mantém a mensagem genérica.
      }
    }
    throw new ApiError(response.status, code, message, requestId);
  }

  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

async function publicRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: "same-origin",
  });
  return parseResponse<T>(response);
}

async function requestRaw(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const headers = new Headers(init.headers);
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const method = (init.method ?? "GET").toUpperCase();
  if (!["GET", "HEAD"].includes(method)) {
    const csrf = currentCsrf();
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: "same-origin",
  });

  if (response.status === 401 && retry && !path.startsWith("/auth/web/")) {
    const refreshed = await refreshSession();
    if (refreshed) {
      return requestRaw(path, init, false);
    }
  }

  return response;
}

async function request<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  return parseResponse<T>(await requestRaw(path, init, retry));
}

async function doRefresh(): Promise<WebSessionPayload | null> {
  const csrf = currentCsrf();
  if (!csrf) return null;

  const response = await fetch(`${API_BASE}/auth/web/refresh`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "X-CSRF-Token": csrf },
  });
  if (response.status === 401 || response.status === 403) {
    clearAuthTokens();
    return null;
  }

  const payload = await parseResponse<WebSessionPayload>(response);
  setAuthTokens({ accessToken: payload.access_token, csrfToken: payload.csrf_token });
  return payload;
}

export function refreshSession(): Promise<WebSessionPayload | null> {
  if (!refreshInFlight) {
    refreshInFlight = doRefresh().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

export async function requestPhoneChallenge(
  phone: string,
  purpose: "login" | "registration",
): Promise<ChallengeResponse> {
  return publicRequest<ChallengeResponse>("/auth/phone/challenges", {
    method: "POST",
    body: JSON.stringify({ phone, purpose }),
  });
}

export async function verifyPhoneChallenge(
  challengeId: string,
  code: string,
): Promise<VerifyResponse> {
  return publicRequest<VerifyResponse>(
    `/auth/phone/challenges/${encodeURIComponent(challengeId)}/verify`,
    {
      method: "POST",
      body: JSON.stringify({ code }),
    },
  );
}

async function webSession(
  path: "/auth/web/login" | "/auth/web/registration",
  challengeId: string,
): Promise<WebSessionPayload> {
  const payload = await publicRequest<WebSessionPayload>(path, {
    method: "POST",
    body: JSON.stringify({
      challenge_id: challengeId,
      device_name: "JOGA y GESTÃO",
    }),
  });
  setAuthTokens({
    accessToken: payload.access_token,
    csrfToken: payload.csrf_token,
  });
  return payload;
}

export function webLogin(challengeId: string): Promise<WebSessionPayload> {
  return webSession("/auth/web/login", challengeId);
}

export function webRegister(challengeId: string): Promise<WebSessionPayload> {
  return webSession("/auth/web/registration", challengeId);
}

export async function webLogout(): Promise<void> {
  const csrf = currentCsrf();
  try {
    if (csrf) {
      await fetch(`${API_BASE}/auth/web/logout`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-CSRF-Token": csrf },
      });
    }
  } finally {
    clearAuthTokens();
  }
}

function memberPath(organizationId: string, userId: string): string {
  return `/organizations/${encodeURIComponent(organizationId)}/members/${encodeURIComponent(
    userId,
  )}`;
}

function venuePath(organizationId: string, venueId?: string): string {
  const base = `/organizations/${encodeURIComponent(organizationId)}/venues`;
  return venueId ? `${base}/${encodeURIComponent(venueId)}` : base;
}

function venueBase(organizationId: string, venueId: string): string {
  return venuePath(organizationId, venueId);
}

export const api = {
  listOrganizations(): Promise<OrganizationListResponse> {
    return request<OrganizationListResponse>("/organizations");
  },

  createOrganization(name: string): Promise<Organization> {
    return request<Organization>("/organizations", {
      method: "POST",
      body: JSON.stringify({ name }),
    });
  },

  getOrganization(organizationId: string): Promise<Organization> {
    return request<Organization>(`/organizations/${encodeURIComponent(organizationId)}`);
  },

  updateOrganization(organizationId: string, name: string): Promise<Organization> {
    return request<Organization>(`/organizations/${encodeURIComponent(organizationId)}`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    });
  },

  listMembers(organizationId: string): Promise<MemberListResponse> {
    return request<MemberListResponse>(
      `/organizations/${encodeURIComponent(organizationId)}/members`,
    );
  },

  addMember(organizationId: string, userId: string, role: Role): Promise<Member> {
    return request<Member>(`/organizations/${encodeURIComponent(organizationId)}/members`, {
      method: "POST",
      body: JSON.stringify({ user_id: userId, role }),
    });
  },

  changeMemberRole(organizationId: string, userId: string, role: Role): Promise<Member> {
    return request<Member>(memberPath(organizationId, userId), {
      method: "PATCH",
      body: JSON.stringify({ role }),
    });
  },

  removeMember(organizationId: string, userId: string): Promise<void> {
    return request<void>(memberPath(organizationId, userId), { method: "DELETE" });
  },

  listVenues(organizationId: string): Promise<VenueListResponse> {
    return request<VenueListResponse>(venuePath(organizationId));
  },

  getVenue(organizationId: string, venueId: string): Promise<Venue> {
    return request<Venue>(venuePath(organizationId, venueId));
  },

  createVenue(
    organizationId: string,
    payload: {
      name: string;
      city: string | null;
      state: string | null;
      address_line: string | null;
    },
  ): Promise<Venue> {
    return request<Venue>(venuePath(organizationId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  updateVenue(
    organizationId: string,
    venueId: string,
    payload: Partial<
      Pick<Venue, "name" | "city" | "state" | "address_line" | "timezone" | "status">
    >,
  ): Promise<Venue> {
    return request<Venue>(venuePath(organizationId, venueId), {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  listAudit(organizationId: string): Promise<AuditListResponse> {
    return request<AuditListResponse>(
      `/organizations/${encodeURIComponent(organizationId)}/audit?limit=50`,
    );
  },

  listSports(): Promise<SportCatalogResponse> {
    return request<SportCatalogResponse>("/sports");
  },

  listSpaces(organizationId: string, venueId: string): Promise<VenueSpaceListResponse> {
    return request<VenueSpaceListResponse>(`${venueBase(organizationId, venueId)}/spaces`);
  },

  createSpace(
    organizationId: string,
    venueId: string,
    payload: { name: string; description: string | null },
  ): Promise<VenueSpace> {
    return request<VenueSpace>(`${venueBase(organizationId, venueId)}/spaces`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  updateSpace(
    organizationId: string,
    venueId: string,
    spaceId: string,
    payload: Partial<Pick<VenueSpace, "name" | "description" | "status">>,
  ): Promise<VenueSpace> {
    return request<VenueSpace>(
      `${venueBase(organizationId, venueId)}/spaces/${encodeURIComponent(spaceId)}`,
      {
        method: "PATCH",
        body: JSON.stringify(payload),
      },
    );
  },

  deleteSpace(organizationId: string, venueId: string, spaceId: string): Promise<void> {
    return request<void>(
      `${venueBase(organizationId, venueId)}/spaces/${encodeURIComponent(spaceId)}`,
      { method: "DELETE" },
    );
  },

  replaceSpaceSports(
    organizationId: string,
    venueId: string,
    spaceId: string,
    sportIds: string[],
  ): Promise<VenueSpace["sports"]> {
    return request<VenueSpace["sports"]>(
      `${venueBase(organizationId, venueId)}/spaces/${encodeURIComponent(spaceId)}/sports`,
      {
        method: "PUT",
        body: JSON.stringify({ sport_ids: sportIds }),
      },
    );
  },

  listAvailability(
    organizationId: string,
    venueId: string,
    spaceId: string,
  ): Promise<VenueAvailabilityListResponse> {
    return request<VenueAvailabilityListResponse>(
      `${venueBase(organizationId, venueId)}/spaces/${encodeURIComponent(spaceId)}/availability`,
    );
  },

  createAvailability(
    organizationId: string,
    venueId: string,
    spaceId: string,
    payload: {
      weekday: number;
      start_time: string;
      end_time: string;
      price_cents: number;
      slot_minutes: number;
    },
  ): Promise<VenueAvailability> {
    return request<VenueAvailability>(
      `${venueBase(organizationId, venueId)}/spaces/${encodeURIComponent(spaceId)}/availability`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  },

  deleteAvailability(
    organizationId: string,
    venueId: string,
    spaceId: string,
    availabilityId: string,
  ): Promise<void> {
    return request<void>(
      `${venueBase(organizationId, venueId)}/spaces/${encodeURIComponent(
        spaceId,
      )}/availability/${encodeURIComponent(availabilityId)}`,
      { method: "DELETE" },
    );
  },

  listBlackouts(
    organizationId: string,
    venueId: string,
    spaceId: string,
  ): Promise<VenueBlackoutListResponse> {
    return request<VenueBlackoutListResponse>(
      `${venueBase(organizationId, venueId)}/spaces/${encodeURIComponent(spaceId)}/blackouts`,
    );
  },

  createBlackout(
    organizationId: string,
    venueId: string,
    spaceId: string,
    payload: {
      starts_at: string;
      ends_at: string;
      reason: string;
      external_reference: string | null;
    },
  ): Promise<VenueBlackout> {
    return request<VenueBlackout>(
      `${venueBase(organizationId, venueId)}/spaces/${encodeURIComponent(spaceId)}/blackouts`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  },

  deleteBlackout(
    organizationId: string,
    venueId: string,
    spaceId: string,
    blackoutId: string,
  ): Promise<void> {
    return request<void>(
      `${venueBase(organizationId, venueId)}/spaces/${encodeURIComponent(
        spaceId,
      )}/blackouts/${encodeURIComponent(blackoutId)}`,
      { method: "DELETE" },
    );
  },

  listPhotos(organizationId: string, venueId: string): Promise<VenuePhotoListResponse> {
    return request<VenuePhotoListResponse>(`${venueBase(organizationId, venueId)}/photos`);
  },

  async uploadPhoto(
    organizationId: string,
    venueId: string,
    payload: { file: File; caption?: string; spaceId?: string },
  ): Promise<VenuePhoto> {
    const form = new FormData();
    form.set("file", payload.file);
    if (payload.caption) form.set("caption", payload.caption);
    if (payload.spaceId) form.set("space_id", payload.spaceId);
    const response = await requestRaw(`${venueBase(organizationId, venueId)}/photos`, {
      method: "POST",
      body: form,
    });
    return parseResponse<VenuePhoto>(response);
  },

  reviewPhoto(
    organizationId: string,
    venueId: string,
    photoId: string,
    decision: "APPROVED" | "REJECTED",
    reason?: string,
  ): Promise<VenuePhoto> {
    return request<VenuePhoto>(
      `${venueBase(organizationId, venueId)}/photos/${encodeURIComponent(photoId)}/review`,
      {
        method: "POST",
        body: JSON.stringify({ decision, reason: reason ?? null }),
      },
    );
  },

  removePhoto(organizationId: string, venueId: string, photoId: string): Promise<void> {
    return request<void>(
      `${venueBase(organizationId, venueId)}/photos/${encodeURIComponent(photoId)}`,
      { method: "DELETE" },
    );
  },

  async fetchPhoto(contentUrl: string): Promise<Blob> {
    const path = contentUrl.startsWith(API_BASE) ? contentUrl.slice(API_BASE.length) : contentUrl;
    const response = await requestRaw(path);
    if (!response.ok) {
      await parseResponse<unknown>(response);
    }
    return response.blob();
  },
};
