import type {
  AuditListResponse,
  Booking,
  BookingFinancialResponse,
  BookingListParams,
  BookingListResponse,
  BusinessHour,
  BusinessHourListResponse,
  ChallengeResponse,
  CommissionResponse,
  FinancialDispute,
  FinancialDisputeListResponse,
  FinancialStatementListResponse,
  GeocodingPrecision,
  MarkAllReadResponse,
  Member,
  MemberListResponse,
  ModerationAppeal,
  ModerationOperator,
  ModerationQueue,
  ModerationReport,
  ModeratorMe,
  OperatorNotification,
  OperatorNotificationListResponse,
  Organization,
  OrganizationFinancialSummary,
  OrganizationListResponse,
  PostalCodeLookup,
  Presence,
  PricingBand,
  ReceivableListResponse,
  Role,
  SportCatalogResponse,
  Venue,
  VenueAvailability,
  VenueAvailabilityListResponse,
  VenueBlackout,
  VenueBlackoutListResponse,
  VenueClosure,
  VenueClosureListResponse,
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

export const SESSION_EXPIRED_EVENT = "joga:session-expired";

let accessToken: string | null = null;
let csrfToken: string | null = null;
let refreshInFlight: Promise<WebSessionPayload | null> | null = null;

export interface ValidationField {
  field: string;
  code: string;
  message: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string | null;
  readonly fields: ValidationField[];
  readonly retryAfterSeconds: number | null;

  constructor(
    status: number,
    code: string,
    message?: string,
    requestId?: string | null,
    fields?: ValidationField[],
    retryAfterSeconds?: number | null,
  ) {
    super(message ?? code);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId ?? null;
    this.fields = fields ?? [];
    this.retryAfterSeconds = retryAfterSeconds ?? null;
  }
}

function parseRetryAfter(value: string | null): number | null {
  if (!value) return null;
  const seconds = Number(value.trim());
  if (!Number.isFinite(seconds) || seconds < 0) return null;
  return Math.ceil(seconds);
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
  const retryAfterSeconds = parseRetryAfter(response.headers.get("retry-after"));
  const text = await response.text();
  if (!response.ok) {
    let code = "request_failed";
    let message = `Falha na requisição (${response.status}).`;
    let fields: ValidationField[] = [];
    if (text) {
      try {
        const body = JSON.parse(text) as { detail?: unknown };
        if (typeof body.detail === "object" && body.detail !== null) {
          const detail = body.detail as {
            code?: unknown;
            message?: unknown;
            fields?: unknown;
          };
          if (typeof detail.code === "string") code = detail.code;
          if (typeof detail.message === "string") message = detail.message;
          if (Array.isArray(detail.fields)) {
            fields = detail.fields
              .filter(
                (field): field is ValidationField =>
                  typeof field === "object" &&
                  field !== null &&
                  typeof (field as ValidationField).field === "string" &&
                  typeof (field as ValidationField).code === "string" &&
                  typeof (field as ValidationField).message === "string",
              )
              .map((field) => ({
                field: field.field,
                code: field.code,
                message: field.message,
              }));
          }
        } else if (typeof body.detail === "string") {
          message = body.detail;
        }
      } catch {
        // Resposta não JSON: mantém a mensagem genérica.
      }
    }
    throw new ApiError(response.status, code, message, requestId, fields, retryAfterSeconds);
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
    clearAuthTokens();
    if (typeof window !== "undefined") {
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
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

  updatePayout(
    organizationId: string,
    payload: { legal_document: string; pix_key_type: string; pix_key: string },
  ): Promise<Organization> {
    return request<Organization>(`/organizations/${encodeURIComponent(organizationId)}/payout`, {
      method: "PUT",
      body: JSON.stringify(payload),
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

  lookupPostalCode(postalCode: string, number?: string | null): Promise<PostalCodeLookup> {
    const cep = postalCode.replace(/\D/g, "");
    const trimmed = number?.trim();
    const query = trimmed ? `?number=${encodeURIComponent(trimmed)}` : "";
    return request<PostalCodeLookup>(`/geo/postal-codes/${encodeURIComponent(cep)}${query}`);
  },

  createVenue(
    organizationId: string,
    payload: {
      name: string;
      city: string | null;
      state: string | null;
      address_line: string | null;
      latitude: number;
      longitude: number;
      postal_code?: string | null;
      geocoding_source?: string | null;
      geocoding_precision?: GeocodingPrecision | "manual" | null;
      timezone?: string | null;
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
      Pick<
        Venue,
        | "name"
        | "city"
        | "state"
        | "address_line"
        | "latitude"
        | "longitude"
        | "postal_code"
        | "geocoding_source"
        | "geocoding_precision"
        | "timezone"
        | "status"
      >
    >,
  ): Promise<Venue> {
    return request<Venue>(venuePath(organizationId, venueId), {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  listAudit(organizationId: string, limit = 50, offset = 0): Promise<AuditListResponse> {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    return request<AuditListResponse>(
      `/organizations/${encodeURIComponent(organizationId)}/audit?${params.toString()}`,
    );
  },

  listOrganizationBookings(
    organizationId: string,
    params: BookingListParams = {},
  ): Promise<BookingListResponse> {
    const query = new URLSearchParams();
    if (params.status) query.set("status", params.status);
    if (params.from) query.set("from", params.from);
    if (params.to) query.set("to", params.to);
    query.set("limit", String(params.limit ?? 50));
    query.set("offset", String(params.offset ?? 0));
    return request<BookingListResponse>(
      `/organizations/${encodeURIComponent(organizationId)}/bookings?${query.toString()}`,
    );
  },

  getOrganizationFinancialSummary(organizationId: string): Promise<OrganizationFinancialSummary> {
    return request<OrganizationFinancialSummary>(
      `/organizations/${encodeURIComponent(organizationId)}/financial/summary`,
    );
  },

  listReceivables(
    organizationId: string,
    options: { status?: string | null; limit?: number; offset?: number } = {},
  ): Promise<ReceivableListResponse> {
    const params = new URLSearchParams({
      limit: String(options.limit ?? 50),
      offset: String(options.offset ?? 0),
    });
    if (options.status) params.set("status", options.status);
    return request<ReceivableListResponse>(
      `/organizations/${encodeURIComponent(organizationId)}/financial/receivables?${params.toString()}`,
    );
  },

  getFinancialStatement(
    organizationId: string,
    limit = 50,
    offset = 0,
  ): Promise<FinancialStatementListResponse> {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    return request<FinancialStatementListResponse>(
      `/organizations/${encodeURIComponent(organizationId)}/financial/statement?${params.toString()}`,
    );
  },

  listFinancialDisputes(
    organizationId: string,
    options: { status?: string | null; limit?: number; offset?: number } = {},
  ): Promise<FinancialDisputeListResponse> {
    const params = new URLSearchParams({
      limit: String(options.limit ?? 50),
      offset: String(options.offset ?? 0),
    });
    if (options.status) params.set("status", options.status);
    return request<FinancialDisputeListResponse>(
      `/organizations/${encodeURIComponent(organizationId)}/financial/disputes?${params.toString()}`,
    );
  },

  getFinancialCommission(
    organizationId: string,
    options: { from?: string | null; to?: string | null; limit?: number; offset?: number } = {},
  ): Promise<CommissionResponse> {
    const params = new URLSearchParams({
      limit: String(options.limit ?? 50),
      offset: String(options.offset ?? 0),
    });
    if (options.from) params.set("from", options.from);
    if (options.to) params.set("to", options.to);
    return request<CommissionResponse>(
      `/organizations/${encodeURIComponent(organizationId)}/financial/commission?${params.toString()}`,
    );
  },

  openFinancialDispute(
    organizationId: string,
    payload: { booking_id: string; reason: string; evidence?: string | null },
  ): Promise<FinancialDispute> {
    return request<FinancialDispute>(
      `/organizations/${encodeURIComponent(organizationId)}/financial/disputes`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  },

  getFinancialDispute(organizationId: string, disputeId: string): Promise<FinancialDispute> {
    return request<FinancialDispute>(
      `/organizations/${encodeURIComponent(organizationId)}/financial/disputes/${encodeURIComponent(
        disputeId,
      )}`,
    );
  },

  decideFinancialDispute(
    organizationId: string,
    disputeId: string,
    payload: { decision: "ACCEPTED" | "REJECTED"; reason: string },
  ): Promise<FinancialDispute> {
    return request<FinancialDispute>(
      `/organizations/${encodeURIComponent(organizationId)}/financial/disputes/${encodeURIComponent(
        disputeId,
      )}/decision`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  },

  acceptBooking(organizationId: string, bookingId: string): Promise<Booking> {
    return request<Booking>(
      `/organizations/${encodeURIComponent(organizationId)}/bookings/${encodeURIComponent(
        bookingId,
      )}/accept`,
      { method: "POST" },
    );
  },

  declineBooking(organizationId: string, bookingId: string, reason: string): Promise<Booking> {
    return request<Booking>(
      `/organizations/${encodeURIComponent(organizationId)}/bookings/${encodeURIComponent(
        bookingId,
      )}/decline`,
      {
        method: "POST",
        body: JSON.stringify({ reason }),
      },
    );
  },

  completeBooking(organizationId: string, bookingId: string): Promise<Booking> {
    return request<Booking>(
      `/organizations/${encodeURIComponent(organizationId)}/bookings/${encodeURIComponent(
        bookingId,
      )}/complete`,
      { method: "POST" },
    );
  },

  cancelBookingByVenue(
    organizationId: string,
    bookingId: string,
    reason: string,
  ): Promise<Booking> {
    return request<Booking>(
      `/organizations/${encodeURIComponent(organizationId)}/bookings/${encodeURIComponent(
        bookingId,
      )}/cancel`,
      {
        method: "POST",
        body: JSON.stringify({ reason }),
      },
    );
  },

  refundBooking(
    organizationId: string,
    bookingId: string,
    reason: string,
  ): Promise<{ refunded: number }> {
    return request<{ refunded: number }>(
      `/organizations/${encodeURIComponent(organizationId)}/bookings/${encodeURIComponent(
        bookingId,
      )}/refund`,
      {
        method: "POST",
        body: JSON.stringify({ reason }),
      },
    );
  },

  getBookingFinancial(
    organizationId: string,
    bookingId: string,
  ): Promise<BookingFinancialResponse> {
    return request<BookingFinancialResponse>(
      `/organizations/${encodeURIComponent(organizationId)}/bookings/${encodeURIComponent(
        bookingId,
      )}/financial`,
    );
  },

  listPresence(bookingId: string): Promise<{ participants: Presence[] }> {
    return request<{ participants: Presence[] }>(
      `/bookings/${encodeURIComponent(bookingId)}/presence`,
    );
  },

  confirmPresence(bookingId: string, userId: string, method: "VENUE" | "GPS"): Promise<Presence> {
    return request<Presence>(`/bookings/${encodeURIComponent(bookingId)}/presence`, {
      method: "POST",
      body: JSON.stringify({ target_user_id: userId, method }),
    });
  },

  listSports(): Promise<SportCatalogResponse> {
    return request<SportCatalogResponse>("/sports");
  },

  listBands(): Promise<{ bands: PricingBand[] }> {
    return request<{ bands: PricingBand[] }>("/pricing/bands");
  },

  listSpaces(organizationId: string, venueId: string): Promise<VenueSpaceListResponse> {
    return request<VenueSpaceListResponse>(`${venueBase(organizationId, venueId)}/spaces`);
  },

  createSpace(
    organizationId: string,
    venueId: string,
    payload: { name: string; description: string | null; is_covered?: boolean },
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
    payload: Partial<Pick<VenueSpace, "name" | "description" | "status" | "is_covered">>,
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

  updateAvailability(
    organizationId: string,
    venueId: string,
    spaceId: string,
    availabilityId: string,
    payload: Partial<{
      weekday: number;
      start_time: string;
      end_time: string;
      price_cents: number;
      slot_minutes: number;
    }>,
  ): Promise<VenueAvailability> {
    return request<VenueAvailability>(
      `${venueBase(organizationId, venueId)}/spaces/${encodeURIComponent(
        spaceId,
      )}/availability/${encodeURIComponent(availabilityId)}`,
      {
        method: "PATCH",
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

  listBusinessHours(organizationId: string, venueId: string): Promise<BusinessHourListResponse> {
    return request<BusinessHourListResponse>(
      `${venueBase(organizationId, venueId)}/business-hours`,
    );
  },

  createBusinessHour(
    organizationId: string,
    venueId: string,
    payload: { weekday: number; opens_at: string; closes_at: string },
  ): Promise<BusinessHour> {
    return request<BusinessHour>(`${venueBase(organizationId, venueId)}/business-hours`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  updateBusinessHour(
    organizationId: string,
    venueId: string,
    businessHourId: string,
    payload: Partial<{ weekday: number; opens_at: string; closes_at: string }>,
  ): Promise<BusinessHour> {
    return request<BusinessHour>(
      `${venueBase(organizationId, venueId)}/business-hours/${encodeURIComponent(businessHourId)}`,
      {
        method: "PATCH",
        body: JSON.stringify(payload),
      },
    );
  },

  deleteBusinessHour(
    organizationId: string,
    venueId: string,
    businessHourId: string,
  ): Promise<void> {
    return request<void>(
      `${venueBase(organizationId, venueId)}/business-hours/${encodeURIComponent(businessHourId)}`,
      { method: "DELETE" },
    );
  },

  listClosures(organizationId: string, venueId: string): Promise<VenueClosureListResponse> {
    return request<VenueClosureListResponse>(`${venueBase(organizationId, venueId)}/closures`);
  },

  createClosure(
    organizationId: string,
    venueId: string,
    payload: { starts_at: string; ends_at: string; reason: string },
  ): Promise<VenueClosure> {
    return request<VenueClosure>(`${venueBase(organizationId, venueId)}/closures`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  deleteClosure(organizationId: string, venueId: string, closureId: string): Promise<void> {
    return request<void>(
      `${venueBase(organizationId, venueId)}/closures/${encodeURIComponent(closureId)}`,
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

  getModeratorMe(): Promise<ModeratorMe> {
    return request<ModeratorMe>("/moderation/me");
  },

  getModerationQueue(statusFilter = "OPEN", limit = 30, offset = 0): Promise<ModerationQueue> {
    const query = new URLSearchParams({
      status_filter: statusFilter,
      limit: String(limit),
      offset: String(offset),
    });
    return request<ModerationQueue>(`/moderation/queue?${query.toString()}`);
  },

  getModerationReport(reportId: string): Promise<ModerationReport> {
    return request<ModerationReport>(`/moderation/reports/${encodeURIComponent(reportId)}`);
  },

  decideModerationReport(
    reportId: string,
    payload: { decision: string; reason: string; days?: number },
  ): Promise<ModerationReport> {
    return request<ModerationReport>(
      `/moderation/reports/${encodeURIComponent(reportId)}/decision`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  },

  listModerationAppeals(): Promise<ModerationAppeal[]> {
    return request<ModerationAppeal[]>("/moderation/appeals?status_filter=OPEN");
  },

  decideModerationAppeal(
    appealId: string,
    payload: { decision: "ACCEPTED" | "REJECTED"; reason: string },
  ): Promise<ModerationAppeal> {
    return request<ModerationAppeal>(
      `/moderation/appeals/${encodeURIComponent(appealId)}/decision`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  },

  listModerationOperators(): Promise<ModerationOperator[]> {
    return request<ModerationOperator[]>("/moderation/operators");
  },

  upsertModerationOperator(
    userId: string,
    role: "ADMIN" | "MODERATOR",
  ): Promise<ModerationOperator> {
    return request<ModerationOperator>("/moderation/operators", {
      method: "POST",
      body: JSON.stringify({ user_id: userId, role }),
    });
  },

  removeModerationOperator(userId: string): Promise<void> {
    return request<void>(`/moderation/operators/${encodeURIComponent(userId)}`, {
      method: "DELETE",
    });
  },

  listModerationNotifications(
    params: { unreadOnly?: boolean; limit?: number; offset?: number } = {},
  ): Promise<OperatorNotificationListResponse> {
    const query = new URLSearchParams();
    if (params.unreadOnly) query.set("unread_only", "true");
    query.set("limit", String(params.limit ?? 30));
    query.set("offset", String(params.offset ?? 0));
    return request<OperatorNotificationListResponse>(
      `/moderation/notifications?${query.toString()}`,
    );
  },

  getModerationNotificationsUnreadCount(): Promise<{ unread_count: number }> {
    return request<{ unread_count: number }>("/moderation/notifications/unread-count");
  },

  markModerationNotificationRead(notificationId: string): Promise<OperatorNotification> {
    return request<OperatorNotification>(
      `/moderation/notifications/${encodeURIComponent(notificationId)}/read`,
      { method: "POST" },
    );
  },

  markAllModerationNotificationsRead(): Promise<MarkAllReadResponse> {
    return request<MarkAllReadResponse>("/moderation/notifications/read-all", { method: "POST" });
  },
};
