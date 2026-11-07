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
  photos: (organizationId: string, venueId: string) =>
    ["organizations", organizationId, "venues", venueId, "photos"] as const,
  bookings: (organizationId: string) => ["organizations", organizationId, "bookings"] as const,
  financialSummary: (organizationId: string) =>
    ["organizations", organizationId, "financial-summary"] as const,
  sports: ["sports"] as const,
  audit: (organizationId: string) => ["organizations", organizationId, "audit"] as const,
};
