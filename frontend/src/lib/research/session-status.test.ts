import { describe, it, expect } from "vitest";
import { isTerminalSessionStatus } from "./session-status";

describe("isTerminalSessionStatus", () => {
  it.each(["article_complete", "article_failed", "failed", "cancelled", "completed"])(
    "treats %s as terminal",
    (status) => {
      expect(isTerminalSessionStatus(status)).toBe(true);
    },
  );

  it.each(["planning", "in_progress", "researching", "evaluating", "running", "complete", "generating_article"])(
    "treats %s as non-terminal",
    (status) => {
      expect(isTerminalSessionStatus(status)).toBe(false);
    },
  );

  it("treats null/undefined as non-terminal", () => {
    expect(isTerminalSessionStatus(null)).toBe(false);
    expect(isTerminalSessionStatus(undefined)).toBe(false);
  });
});
