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
  capabilities: string[];
}

export interface Organization {
  id: string;
  name: string;
  status: string;
  role: Role;
  payout_ready: boolean;
  payout_status: string;
  pix_key_type: string | null;
  pix_key_masked: string | null;
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
  latitude: number | null;
  longitude: number | null;
  postal_code: string | null;
  geocoding_source: string | null;
  geocoding_precision: GeocodingPrecision | "manual" | null;
  geocoded_at: string | null;
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
  is_covered: boolean;
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
  band_id: string | null;
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

export interface BusinessHour {
  id: string;
  weekday: number;
  opens_at: string;
  closes_at: string;
}

export interface BusinessHourListResponse {
  business_hours: BusinessHour[];
}

export interface VenueClosure {
  id: string;
  starts_at: string;
  ends_at: string;
  reason: string;
  created_at: string;
}

export interface VenueClosureListResponse {
  closures: VenueClosure[];
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
  settled_with: string | null;
  tickets_consumed: number;
  presence_status: string;
  presence_method: string | null;
  presence_confirmed_at: string | null;
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
  organization_venue_name: string | null;
  venue_space_name: string | null;
  format_id: string | null;
  format_name: string | null;
  band_code: string | null;
  band_label: string | null;
  tickets_per_seat: number | null;
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
  presence_closed_at: string | null;
  players_per_team: number | null;
  formation_note: string | null;
  cancellation_reason: string | null;
  created_at: string;
  updated_at: string;
  participants: BookingParticipant[];
  timers: BookingTimer[];
  hold: BookingHold | null;
  payments: BookingPayment[];
  timezone: string | null;
}

export interface BookingListResponse {
  bookings: Booking[];
  total: number;
  limit: number;
  offset: number;
}

export interface BookingListParams {
  status?: string | null;
  from?: string | null;
  to?: string | null;
  limit?: number;
  offset?: number;
}

export interface OrganizationFinancialSummary {
  charged_cents: number;
  paid_cents: number;
  refunded_cents: number;
  pending_cents: number;
  released_cents: number;
  pending_release_cents: number;
  disputed_cents: number;
  payments: number;
  refunds: number;
}

export type ReleaseStatus = "PENDING" | "RELEASED" | "FAILED" | "REVERSED";
export type DisputeStatus = "OPEN" | "ACCEPTED" | "REJECTED" | "WITHDRAWN";

export interface Receivable {
  booking_id: string;
  release_id: string;
  amount_cents: number;
  status: ReleaseStatus;
  eligible_at: string;
  released_at: string | null;
  starts_at: string;
  ends_at: string;
  has_open_dispute: boolean;
  dispute_id: string | null;
}

export interface ReceivableListResponse {
  receivables: Receivable[];
  total: number;
  limit: number;
  offset: number;
}

export interface FinancialStatementEntry {
  id: string;
  booking_id: string;
  booking_payment_id: string | null;
  entry_type: string;
  direction: "CREDIT" | "DEBIT";
  amount_cents: number;
  status: string;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface BookingRefund {
  id: string;
  booking_payment_id: string;
  amount_cents: number;
  status: "PENDING" | "PROCESSED" | "FAILED" | string;
  reason: string | null;
  provider_reference: string | null;
  processed_at: string | null;
  created_at: string;
}

export interface BookingFinancialResponse {
  booking_id: string;
  ledger: FinancialStatementEntry[];
  refunds: BookingRefund[];
}

export interface FinancialStatementListResponse {
  entries: FinancialStatementEntry[];
  total: number;
  limit: number;
  offset: number;
}

export interface FinancialDispute {
  id: string;
  organization_id: string;
  booking_id: string;
  release_id: string | null;
  amount_cents: number;
  status: DisputeStatus;
  reason: string;
  evidence: string | null;
  decision_reason: string | null;
  decided_by: string | null;
  decided_at: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface FinancialDisputeListResponse {
  disputes: FinancialDispute[];
  total: number;
  limit: number;
  offset: number;
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
  total: number;
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

export interface PricingBand {
  id: string;
  code: string;
  label: string;
  max_price_cents: number;
  version: number;
}

export interface Presence {
  user_id: string;
  seat: number;
  active: boolean;
  pre_checked_in_at: string | null;
  status: string;
  method: string | null;
  confirmed_at: string | null;
  distance_m: number | null;
  accuracy_m: number | null;
}

export interface ModeratorMe {
  user_id: string;
  role: "ADMIN" | "MODERATOR";
}

export interface ModerationContextMessage {
  id: string;
  sender_id: string;
  body: string;
  created_at: string;
}

export interface ModerationReport {
  id: string;
  category: string;
  status: string;
  severity: string;
  priority: number;
  created_at: string;
  reviewed_at: string | null;
  decision_reason: string | null;
  reporter_id: string;
  target_user_id: string;
  lobby_id: string;
  description: string;
  context: ModerationContextMessage[];
  classifier_version: string;
  classifier_signals: Record<string, unknown> | null;
  reviewed_by: string | null;
}

export interface ModerationQueue {
  reports: ModerationReport[];
  stats: {
    open: number;
    in_review: number;
    appealed: number;
    high_priority: number;
  };
}

export interface ModerationAppeal {
  id: string;
  action_id: string;
  status: string;
  reason: string;
  created_at: string;
  decided_at: string | null;
  decision_reason: string | null;
}

export interface ModerationOperator {
  user_id: string;
  role: "ADMIN" | "MODERATOR";
  active: boolean;
  created_at: string;
  deactivated_at: string | null;
}

export interface OperatorNotification {
  id: string;
  kind: string;
  title: string;
  body: string;
  data: Record<string, unknown> | null;
  created_at: string;
  read_at: string | null;
}

export interface OperatorNotificationListResponse {
  notifications: OperatorNotification[];
  unread_count: number;
  limit: number;
  offset: number;
}

export interface MarkAllReadResponse {
  marked: number;
  unread_count: number;
}

export type GeocodingPrecision = "street" | "venue" | "approximate" | "unresolved";

export interface PostalCodeLookup {
  postal_code: string;
  street: string | null;
  neighborhood: string | null;
  city: string;
  state: string;
  country: string;
  latitude: number | null;
  longitude: number | null;
  precision: GeocodingPrecision;
  source: string;
  resolved_at: string;
}
