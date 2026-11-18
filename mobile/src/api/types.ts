export type Challenge = {
  challenge_id: string;
  expires_at: string;
  resend_after_seconds: number;
};

export type EmailVerification = {
  challenge_id: string;
  purpose: string;
  verified_at: string;
  receipt_expires_at: string;
};

export type EmailCredential = {
  email: string;
  is_primary: boolean;
  verified_at: string | null;
  created_at: string;
};

export type Tokens = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  access_expires_at: string;
  refresh_expires_at: string;
  user: { id: string; status: string };
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

export type Sport = { id: string; slug: string; name: string; formats: SportFormat[] };

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

export type VenuePage = { items: Venue[]; total: number; page: number; page_size: number };

export type BookableVenue = {
  id: string;
  organization_id: string;
  name: string;
  city: string;
  state: string;
  address_line: string | null;
  latitude: number;
  longitude: number;
  timezone: string;
  covered: boolean;
  spaces_count: number;
  min_price_cents: number;
  distance_km: number | null;
  photo_url: string | null;
};

export type BookableVenuePage = {
  venues: BookableVenue[];
  total: number;
  page: number;
  page_size: number;
};

export type BookableVenuePhoto = {
  id: string;
  caption: string | null;
  content_type: string;
  content_url: string;
};

export type BookableVenueBand = {
  id: string;
  code: string;
  label: string;
  max_price_cents: number;
};

export type BookableVenueAvailability = {
  weekday: number;
  start_time: string;
  end_time: string;
  price_cents: number;
  slot_minutes: number;
  band: BookableVenueBand | null;
};

export type BookableVenueNextSlot = {
  starts_at: string;
  ends_at: string;
  price_cents: number;
  band_code: string;
};

export type BookableVenueFormat = {
  id: string;
  slug: string;
  name: string;
  team_size: number;
  total_participants: number;
  tickets_by_band: Record<string, number>;
};

export type BookableVenueSport = {
  id: string;
  slug: string;
  name: string;
  formats: BookableVenueFormat[];
};

export type BookableVenueSpace = {
  id: string;
  name: string;
  is_covered: boolean;
  sports: BookableVenueSport[];
  availability: BookableVenueAvailability[];
  next_slots: BookableVenueNextSlot[];
};

export type BookableVenueDetail = {
  id: string;
  organization_id: string;
  name: string;
  timezone: string;
  photos: BookableVenuePhoto[];
  spaces: BookableVenueSpace[];
};

export type QueueLobby = {
  id: string;
  mode: string;
  court_preference: string;
  scheduled_start_at: string;
  scheduled_end_at: string;
  duration_minutes: number;
};

export type QueueEntry = {
  id: string;
  format_id: string;
  mode: string;
  court_preference: string;
  level: string;
  status: string;
  radius_km: number;
  created_at: string;
  expires_at: string;
  lobby: QueueLobby | null;
};

export type MatchParticipant = {
  user_id: string;
  display_name: string | null;
  team: number;
  level: string;
  status: string;
  is_substitute: boolean;
  confirmed_at: string | null;
  checked_in_at: string | null;
};

export type MatchSummary = {
  id: string;
  lobby_id: string;
  state: string;
  scheduled_start_at: string;
  scheduled_end_at: string;
  confirmation_deadline: string;
  check_in_opens_at: string;
  check_in_deadline: string;
  substitution_deadline: string;
  cancelled_reason: string | null;
  my_status: string;
  participants: MatchParticipant[] | null;
};

export type MyRating = {
  format_id: string;
  algorithm_version: string;
  division: string;
  provisional: boolean;
  placement_matches_remaining: number;
  progress: number | null;
  next_division: string | null;
  position: number | null;
  matches_played: number;
  last_rated_at: string | null;
};

export type RankingEntry = {
  position: number;
  user_id: string;
  display_name: string | null;
  division: string;
  matches_played: number;
};

export type Ranking = {
  format_id: string;
  algorithm_version: string;
  placement_matches: number;
  total: number;
  limit: number;
  offset: number;
  entries: RankingEntry[];
};

export type SeasonView = { code: string; starts_at: string; ends_at: string };

export type Progress = {
  season: SeasonView;
  xp_total: number;
  level: number;
  tier: string;
  next_level_xp: number | null;
  streak: { current: number; best: number };
};

export type TrackLevel = {
  level: number;
  xp_required: number;
  item_code: string | null;
  item_name: string | null;
  free_tickets: number;
  track: string;
  claimed: boolean;
  available: boolean;
};

export type Track = {
  season: SeasonView;
  xp_total: number;
  level: number;
  has_pass: boolean;
  levels: TrackLevel[];
};

export type Badge = {
  badge_id: string;
  code: string;
  name: string;
  kind: string;
  equipped_slot: number | null;
  awarded_at: string;
};

export type Mission = {
  code: string;
  progress: number;
  target: number;
  xp_reward: number;
  completed: boolean;
};

export type Wallet = {
  balance: number;
  source: string;
  lots: TicketLot[];
  entries: {
    id: string;
    amount: number;
    source: string;
    ref_type: string | null;
    ref_id: string | null;
    created_at: string;
  }[];
};

export type TicketLot = {
  id: string;
  source: string;
  original_amount: number;
  remaining: number;
  period: string | null;
  expires_at: string | null;
  ref_type: string | null;
  ref_id: string | null;
};

export type TicketPack = {
  code: string;
  label: string;
  tickets: number;
  unit_price_cents: number;
  amount_cents: number;
};

export type PurchasePayment = {
  provider: string | null;
  provider_status: string | null;
  status_detail: string | null;
  external_reference: string | null;
  amount_cents: number | null;
  qr_code: string | null;
  qr_code_base64: string | null;
  ticket_url: string | null;
  expires_at: string | null;
  paid: boolean;
};

export type Purchase = {
  id: string;
  pack_id: string;
  tickets: number;
  amount_cents: number;
  status: string;
  created_at: string;
  paid_at: string | null;
  payment: PurchasePayment | null;
};

export type PassPlan = {
  code: string;
  label: string;
  tickets_per_month: number;
  unit_price_cents: number;
  price_per_month_cents: number;
  quarter_cents: number;
};

export type PassDelivery = { month_index: number; tickets: number; delivered_at: string };

export type PassSubscription = {
  id: string;
  plan_code: string;
  tickets_per_month: number;
  amount_cents: number;
  status: string;
  starts_at: string | null;
  ends_at: string | null;
  paid_at: string | null;
  created_at: string;
  deliveries: PassDelivery[];
  next_delivery_at: string | null;
  payment: PurchasePayment | null;
};

export type Band = {
  id: string;
  code: string;
  label: string;
  max_price_cents: number;
  version: number;
};

export type Stats = {
  totals: {
    matches: number;
    wins: number;
    draws: number;
    losses: number;
    presence_rate: number | null;
    streak_current: number;
    streak_best: number;
  };
  by_format: { format_id: string; name: string; matches: number; wins: number }[];
  has_pass: boolean;
};

export type CourtHistory = {
  space_id: string;
  name: string;
  matches: number;
  wins: number;
  last_played_at: string;
};

export type Passport = {
  totals: Stats['totals'];
  seasons_played: number;
  badges: number;
  courts: number;
};

export type Network = {
  updated_on: string;
  window_days: number;
  min_sample: number;
  sample_size: number;
  has_pass: boolean;
  peak_band: string | null;
  own_hours: string[];
  venues: { space_id: string; name: string; matches: number; level: string }[];
  cells: { space_id: string; space_name: string; band: string; matches: number; level: string }[];
};

export type BookingParticipant = {
  id: string;
  user_id: string;
  seat: number;
  active: boolean;
  contribution_cents: number;
  space_charge_cents: number;
  fee_charge_cents: number;
  funding_source: string | null;
  payment_status: string;
  settled_with: string | null;
  tickets_consumed: number;
  confirmed_at: string | null;
  declined_at: string | null;
  replaced_by_user_id: string | null;
  presence_status: string;
  presence_method: string | null;
  presence_confirmed_at: string | null;
};

export type Presence = {
  user_id: string;
  seat: number;
  active: boolean;
  pre_checked_in_at: string | null;
  status: string;
  method: string | null;
  confirmed_at: string | null;
  distance_m: number | null;
  accuracy_m: number | null;
};

export type BookingTimer = {
  timer_type: string;
  status: string;
  started_at: string;
  deadline_at: string;
  ended_at: string | null;
};

export type BookingPayment = {
  id: string;
  participant_id: string;
  version: number;
  amount_cents: number;
  status: string;
  provider: string | null;
  provider_order_id: string | null;
  provider_payment_id: string | null;
  provider_status: string | null;
  status_detail: string | null;
  external_reference: string | null;
  qr_code: string | null;
  qr_code_base64: string | null;
  ticket_url: string | null;
  expires_at: string | null;
  last_synced_at: string | null;
  paid_at: string | null;
};

export type Booking = {
  id: string;
  lobby_id: string;
  organization_id: string;
  organization_venue_id: string;
  organization_venue_name: string;
  venue_space_id: string;
  venue_space_name: string;
  format_id: string | null;
  format_name: string | null;
  band_code: string | null;
  band_label: string | null;
  tickets_per_seat: number | null;
  status: string;
  starts_at: string;
  ends_at: string;
  price_cents: number;
  venue_price_cents: number;
  fee_cents: number;
  fee_percent_applied: number;
  total_cents: number;
  pricing_version: string;
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
  timezone: string | null;
  participants: BookingParticipant[];
  timers: BookingTimer[];
  hold: {
    id: string;
    space_id: string;
    starts_at: string;
    ends_at: string;
    status: string;
    released_at: string | null;
  } | null;
  payments: BookingPayment[];
};

export type ResultView = {
  match_id: string;
  state: string;
  round: number | null;
  round_status: string | null;
  opens_at: string | null;
  deadline: string | null;
  eligible_count: number | null;
  quorum: number | null;
  valid_votes: number | null;
  can_vote: boolean;
  my_vote: { outcome: string; submitted_at: string } | null;
  aggregate_visible: boolean;
  aggregate: {
    valid_votes: number;
    counts: Record<string, number>;
    leaders: string[];
    evaluated: string | null;
    divergent: number | null;
    divergence_ratio: number | null;
  } | null;
  captain_confirmations_visible: boolean;
  final_result: string | null;
  dispute_id: string | null;
  review: { pending: boolean; reason: string } | null;
};

export type ChatMessage = {
  id: string;
  lobby_id: string;
  sender_id: string;
  body: string;
  created_at: string;
};

export type Friend = { user_id: string; display_name: string | null };

export type LobbyInvite = {
  id: string;
  lobby_id: string;
  inviter_id: string;
  invitee_id: string;
  status: string;
  created_at: string;
  expires_at: string;
  responded_at: string | null;
};

export type Notification = {
  id: string;
  kind: string;
  title: string;
  body: string;
  data: Record<string, unknown>;
  created_at: string;
  read_at: string | null;
};

export type ModerationReport = {
  id: string;
  category: string;
  status: string;
  created_at: string;
  reviewed_at: string | null;
  decision_reason: string | null;
};

export type ModerationAction = {
  id: string;
  action_type: string;
  status: string;
  starts_at: string;
  ends_at: string | null;
  reason: string;
  created_at: string;
  revoked_at: string | null;
};

export type ModerationAppeal = {
  id: string;
  action_id: string;
  status: string;
  reason: string;
  created_at: string;
  decided_at: string | null;
  decision_reason: string | null;
};

export type Clan = {
  id: string;
  name: string;
  tag: string;
  description: string | null;
  join_policy: string;
  members: number;
  max_members: number;
  trophies: number;
  my_role: string | null;
};

export type ClanMember = {
  user_id: string;
  display_name: string | null;
  role: string;
  joined_at: string;
};

export type ClanMessage = {
  id: string;
  sender_id: string;
  display_name: string | null;
  body: string;
  hidden: boolean;
  created_at: string;
};

export type ClanRanking = {
  season_code: string | null;
  format_id: string | null;
  entries: { clan_id: string; name: string; tag: string; trophies: number; position: number }[];
};

export type Substitute = {
  id: string;
  lobby_id: string;
  user_id: string;
  status: string;
  position: number;
  called_at: string | null;
  confirmed_at: string | null;
  played_at: string | null;
  created_at: string;
};

export type Device = {
  id: string;
  name: string | null;
  platform: string;
  last_seen_at: string | null;
  revoked_at: string | null;
};

export type Passkey = {
  credential_id: string;
  name: string | null;
  created_at: string;
  last_used_at: string | null;
};

export type PasskeyOptions = {
  challenge_id: string;
  public_key: Record<string, unknown>;
  expires_at: string;
};

export type CpfStatus = {
  cpf_present: boolean;
  cpf_masked: string | null;
};

export type TermsVersion = {
  id: string;
  version: string;
  content: string;
  published_at: string;
  terms_hash: string;
};

export type TermsAcceptance = {
  id: string;
  terms_version_id: string;
  version: string;
  context: string;
  accepted_at: string;
  terms_hash: string;
};
