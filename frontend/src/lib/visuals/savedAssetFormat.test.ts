import { describe, expect, it } from "vitest";
import { aspectStyle, humanize } from "./savedAssetFormat";

describe("savedAssetFormat", () => {
  it("humanizes snake_case keys", () => {
    expect(humanize("feature_card")).toBe("Feature Card");
    expect(humanize("hero")).toBe("Hero");
  });

  it("maps aspect strings to a CSS aspect-ratio value, defaulting to 16:9", () => {
    expect(aspectStyle("16:9")).toBe("16 / 9");
    expect(aspectStyle("1:1")).toBe("1 / 1");
    expect(aspectStyle("weird")).toBe("16 / 9");
  });
});
