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
  audit: (organizationId: string) => ["organizations", organizationId, "audit"] as const,
};
