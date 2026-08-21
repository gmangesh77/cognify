import { describe, expect, it } from "vitest";
import { hasPreamble, splitBySections } from "./split-sections";

describe("splitBySections / hasPreamble", () => {
  it("treats a body starting with ## as having no preamble", () => {
    const segs = splitBySections("## A\ntext\n\n## B\nmore");
    expect(segs).toHaveLength(2);
    expect(hasPreamble(segs)).toBe(false);
  });

  it("detects a prelude before the first H2", () => {
    const segs = splitBySections("Intro.\n\n## A\ntext");
    expect(segs).toHaveLength(2);
    expect(hasPreamble(segs)).toBe(true);
  });
});
