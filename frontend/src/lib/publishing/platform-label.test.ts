import { describe, expect, it } from "vitest";
import { platformLabel } from "./platform-label";

describe("platformLabel", () => {
  it("special-cases linkedin_post", () => {
    expect(platformLabel("linkedin_post")).toBe("LinkedIn post");
  });

  it("special-cases linkedin", () => {
    expect(platformLabel("linkedin")).toBe("LinkedIn");
  });

  it("title-cases an unknown underscored platform", () => {
    expect(platformLabel("some_new_platform")).toBe("Some New Platform");
  });

  it("capitalizes a plain platform", () => {
    expect(platformLabel("ghost")).toBe("Ghost");
  });
});
