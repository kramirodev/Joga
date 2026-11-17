import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      retry: 1,
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
};
