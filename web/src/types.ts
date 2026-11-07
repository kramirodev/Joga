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
