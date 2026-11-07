export type Role = "OWNER" | "ADMIN" | "OPERATOR";

export interface WebUser {
  id: string;
  status: string;
}

export interface WebSessionPayload {
  access_token: string;
  access_expires_at: string;
  csrf_token: string;
  user: WebUser;
}

export interface Organization {
  id: string;
  name: string;
  status: string;
  role: Role;
  created_at: string;
  updated_at: string;
}

export interface OrganizationListResponse {
  organizations: Organization[];
}

export interface Member {
  user_id: string;
  display_name: string | null;
  role: Role;
  created_at: string;
}

export interface MemberListResponse {
  members: Member[];
}

export interface Venue {
  id: string;
  organization_id: string;
  venue_id: string | null;
  name: string;
  city: string | null;
  state: string | null;
  address_line: string | null;
  timezone: string;
  status: "active" | "inactive";
  created_at: string;
  updated_at: string;
}

export interface VenueListResponse {
  venues: Venue[];
}

export interface VenueSport {
  id: string;
  slug: string;
  name: string;
}

export interface VenueSpace {
  id: string;
  venue_id: string;
  name: string;
  description: string | null;
  status: "active" | "inactive";
  sports: VenueSport[];
  created_at: string;
  updated_at: string;
}

export interface VenueSpaceListResponse {
  spaces: VenueSpace[];
}

export interface VenueAvailability {
  id: string;
  space_id: string;
  weekday: number;
  start_time: string;
  end_time: string;
  price_cents: number;
  slot_minutes: number;
}

export interface VenueAvailabilityListResponse {
  availability: VenueAvailability[];
}

export interface VenueBlackout {
  id: string;
  space_id: string;
  starts_at: string;
  ends_at: string;
  reason: string;
  external_reference: string | null;
  created_at: string;
}

export interface VenueBlackoutListResponse {
  blackouts: VenueBlackout[];
}

export interface VenuePhoto {
  id: string;
  venue_id: string;
  space_id: string | null;
  status: "PENDING" | "APPROVED" | "REJECTED" | "REMOVED";
  content_type: string;
  size_bytes: number;
  width: number;
  height: number;
  caption: string | null;
  rejection_reason: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
  content_url: string;
  can_review: boolean;
}

export interface VenuePhotoListResponse {
  photos: VenuePhoto[];
  can_review: boolean;
}

export interface BookingParticipant {
  id: string;
  user_id: string;
  seat: number;
  active: boolean;
  contribution_cents: number;
  payment_status: string;
  confirmed_at: string | null;
  declined_at: string | null;
  replaced_by_user_id: string | null;
}

export interface BookingTimer {
  timer_type: "T1" | "T2" | "T3";
  status: string;
  started_at: string;
  deadline_at: string;
  ended_at: string | null;
}

export interface BookingHold {
  id: string;
  space_id: string;
  starts_at: string;
  ends_at: string;
  status: string;
  released_at: string | null;
}

export interface BookingPayment {
  id: string;
  participant_id: string;
  version: number;
  amount_cents: number;
  status: string;
  paid_at: string | null;
}

export interface Booking {
  id: string;
  lobby_id: string;
  organization_id: string;
  organization_venue_id: string;
  venue_space_id: string;
  status: string;
  starts_at: string;
  ends_at: string;
  price_cents: number;
  currency: string;
  seats: number;
  policy_version: string;
  cancellation_policy: string;
  response_due_at: string | null;
  payment_due_at: string | null;
  hold_expires_at: string | null;
  accepted_at: string | null;
  confirmed_at: string | null;
  cancelled_at: string | null;
  expired_at: string | null;
  completed_at: string | null;
  cancellation_reason: string | null;
  created_at: string;
  updated_at: string;
  participants: BookingParticipant[];
  timers: BookingTimer[];
  hold: BookingHold | null;
  payments: BookingPayment[];
}

export interface BookingListResponse {
  bookings: Booking[];
}

export interface OrganizationFinancialSummary {
  charged_cents: number;
  paid_cents: number;
  refunded_cents: number;
  pending_cents: number;
  released_cents: number;
  payments: number;
  refunds: number;
}

export interface SportCatalogItem {
  id: string;
  slug: string;
  name: string;
  formats: Array<{ id: string; slug: string; name: string }>;
}

export interface SportCatalogResponse {
  sports: SportCatalogItem[];
}

export interface AuditEvent {
  id: string;
  actor_user_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditListResponse {
  audit: AuditEvent[];
  limit: number;
  offset: number;
}

export interface ChallengeResponse {
  challenge_id: string;
  expires_at: string;
  resend_after_seconds: number;
}

export interface VerifyResponse {
  challenge_id: string;
  purpose: string;
  verified_at: string;
  receipt_expires_at: string;
}
