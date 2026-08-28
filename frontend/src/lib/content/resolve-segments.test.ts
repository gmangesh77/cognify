import { describe, expect, it } from "vitest";
import { changeIds, resolveSegments } from "./resolve-segments";
import type { HumanizeSegment } from "@/types/content";

const SEGS: HumanizeSegment[] = [
  { id: "s0", kind: "equal", before: "A. ", after: "A. ", ops: [] },
  { id: "s1", kind: "change", before: "Old.", after: "New.", ops: [] },
  { id: "s2", kind: "equal", before: " C. ", after: " C. ", ops: [] },
  { id: "s3", kind: "change", before: "Older.", after: "Newer.", ops: [] },
];

describe("resolveSegments", () => {
  it("returns the final text when nothing is rejected", () => {
    expect(resolveSegments(SEGS, new Set())).toBe("A. New. C. Newer.");
  });

  it("restores rejected change segments", () => {
    expect(resolveSegments(SEGS, new Set(["s1"]))).toBe("A. Old. C. Newer.");
    expect(resolveSegments(SEGS, new Set(["s1", "s3"]))).toBe("A. Old. C. Older.");
  });

  it("changeIds lists only change segments in order", () => {
    expect(changeIds(SEGS)).toEqual(["s1", "s3"]);
  });
});
