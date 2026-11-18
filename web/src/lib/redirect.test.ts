import { describe, expect, it } from "vitest";

import { currentPath, safeReturnPath } from "./redirect";

describe("redirecionamento após login", () => {
  it("aceita apenas caminhos internos", () => {
    expect(safeReturnPath("/organizations/org-1?tab=bookings")).toBe(
      "/organizations/org-1?tab=bookings",
    );
    expect(safeReturnPath("//evil.example")).toBe("/");
    expect(safeReturnPath("https://evil.example")).toBe("/");
    expect(safeReturnPath("")).toBe("/");
    expect(safeReturnPath(null)).toBe("/");
  });

  it("monta o caminho atual com query e hash", () => {
    expect(currentPath("/moderation", "?report=1", "#appeals")).toBe(
      "/moderation?report=1#appeals",
    );
  });
});
