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
  name: string;
  city: string | null;
  state: string | null;
  address_line: string | null;
  status: "active" | "inactive";
  created_at: string;
  updated_at: string;
}

export interface VenueListResponse {
  venues: Venue[];
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
