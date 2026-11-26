import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "./api";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      // 401 é tratado uma única vez pelo cliente HTTP (refresh + evento de
      // sessão expirada); repetir a consulta geraria um segundo ciclo inútil.
      retry: (failureCount, error) => {
        if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
          return false;
        }
        return failureCount < 1;
      },
      refetchOnWindowFocus: false,
    },
  },
});

export const queryKeys = {
  organizations: ["organizations"] as const,
  organization: (organizationId: string) => ["organizations", organizationId] as const,
  members: (organizationId: string) => ["organizations", organizationId, "members"] as const,
  venues: (organizationId: string) => ["organizations", organizationId, "venues"] as const,
  venue: (organizationId: string, venueId: string) =>
    ["organizations", organizationId, "venues", venueId] as const,
  spaces: (organizationId: string, venueId: string) =>
    ["organizations", organizationId, "venues", venueId, "spaces"] as const,
  availability: (organizationId: string, venueId: string, spaceId: string) =>
    [
      "organizations",
      organizationId,
      "venues",
      venueId,
      "spaces",
      spaceId,
      "availability",
    ] as const,
  blackouts: (organizationId: string, venueId: string, spaceId: string) =>
    ["organizations", organizationId, "venues", venueId, "spaces", spaceId, "blackouts"] as const,
  businessHours: (organizationId: string, venueId: string) =>
    ["organizations", organizationId, "venues", venueId, "business-hours"] as const,
  closures: (organizationId: string, venueId: string) =>
    ["organizations", organizationId, "venues", venueId, "closures"] as const,
  photos: (organizationId: string, venueId: string) =>
    ["organizations", organizationId, "venues", venueId, "photos"] as const,
  bookings: (organizationId: string) => ["organizations", organizationId, "bookings"] as const,
  financialSummary: (organizationId: string) =>
    ["organizations", organizationId, "financial-summary"] as const,
  receivables: (organizationId: string) =>
    ["organizations", organizationId, "financial-receivables"] as const,
  statement: (organizationId: string) =>
    ["organizations", organizationId, "financial-statement"] as const,
  disputes: (organizationId: string) =>
    ["organizations", organizationId, "financial-disputes"] as const,
  commission: (organizationId: string, from: string | null, to: string | null) =>
    ["organizations", organizationId, "financial-commission", from, to] as const,
  bookingFinancial: (organizationId: string, bookingId: string) =>
    ["organizations", organizationId, "bookings", bookingId, "financial"] as const,
  sports: ["sports"] as const,
  bands: ["pricing-bands"] as const,
  presence: (bookingId: string) => ["bookings", bookingId, "presence"] as const,
  moderatorMe: ["moderator", "me"] as const,
  moderationQueue: (status: string, limit = 30, offset = 0) =>
    ["moderation", "queue", status, limit, offset] as const,
  moderationAppeals: ["moderation", "appeals"] as const,
  moderationReport: (reportId: string) => ["moderation", "report", reportId] as const,
  moderationOperators: ["moderation", "operators"] as const,
  moderationNotifications: (unreadOnly: boolean) =>
    ["moderation", "notifications", unreadOnly ? "unread" : "all"] as const,
  moderationNotificationsUnread: ["moderation", "notifications", "unread-count"] as const,
  audit: (organizationId: string) => ["organizations", organizationId, "audit"] as const,
  adminUsers: (query: string, status: string, page: number) =>
    ["admin", "users", query, status, page] as const,
  adminUser: (userId: string) => ["admin", "users", userId] as const,
  adminUserAudit: (userId: string) => ["admin", "users", userId, "audit"] as const,
  adminSports: ["admin", "sports"] as const,
  adminPricingSuggestion: (teamSize: number, mode: string) =>
    ["admin", "pricing", "suggest", teamSize, mode] as const,
  adminVisualCatalog: ["admin", "visual-catalog"] as const,
  adminVenues: (active: string, page: number) => ["admin", "venues", active, page] as const,
  adminVenueDirectory: (query: string, status: string, visibility: string, page: number) =>
    ["admin", "venues", "directory", query, status, visibility, page] as const,
  adminVenue: (venueId: string) => ["admin", "venues", venueId] as const,
  adminVenueAvailability: (venueId: string) =>
    ["admin", "venues", venueId, "availability"] as const,
  adminVenueBusinessHours: (venueId: string) =>
    ["admin", "venues", venueId, "business-hours"] as const,
  adminObservabilitySummary: (window: string) =>
    ["admin", "observability", "summary", window] as const,
  adminObservabilityEvents: (key: string) =>
    ["admin", "observability", "events", "list", key] as const,
  adminObservabilityEvent: (eventId: string) =>
    ["admin", "observability", "events", "detail", eventId] as const,
  adminObservabilityUser: (userId: string, key: string) =>
    ["admin", "observability", "users", userId, key] as const,
  adminObservabilityIp: (ip: string) => ["admin", "observability", "ips", ip] as const,
};
