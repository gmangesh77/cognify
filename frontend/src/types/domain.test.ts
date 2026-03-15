import { describe, it, expect } from "vitest";
import { getDomainColor, getDomainLabel } from "./domain";

describe("getDomainColor", () => {
  it("returns correct class for known domains", () => {
    expect(getDomainColor("cybersecurity")).toBe("text-domain-cybersecurity");
    expect(getDomainColor("ai-ml")).toBe("text-domain-ai-ml");
  });

  it("returns default class for unknown domain", () => {
    expect(getDomainColor("unknown")).toBe("text-domain-default");
  });
});

describe("getDomainLabel", () => {
  it("returns display label for known domains", () => {
    expect(getDomainLabel("cybersecurity")).toBe("Cybersecurity");
    expect(getDomainLabel("ai-ml")).toBe("AI / ML");
  });

  it("returns raw domain string for unknown domain", () => {
    expect(getDomainLabel("fintech")).toBe("fintech");
  });
});
