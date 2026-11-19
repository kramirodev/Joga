import { describe, expect, it } from "vitest";

import { ApiError } from "./api";
import { queryClient } from "./query";

function retryDecision(failureCount: number, error: Error): boolean {
  const retry = queryClient.getDefaultOptions().queries?.retry;
  if (typeof retry !== "function") {
    throw new Error("A política de retry deveria ser uma função.");
  }
  return retry(failureCount, error);
}

describe("política de retry do React Query", () => {
  it("não repete 401 nem 403", () => {
    expect(retryDecision(0, new ApiError(401, "invalid_token"))).toBe(false);
    expect(retryDecision(0, new ApiError(403, "platform_admin_required"))).toBe(false);
  });

  it("repete um erro transitório apenas uma vez", () => {
    expect(retryDecision(0, new ApiError(503, "request_failed"))).toBe(true);
    expect(retryDecision(1, new ApiError(503, "request_failed"))).toBe(false);
  });
});
