import { describe, it, expect, afterEach } from "vitest";
import { currentRole } from "./role";

function token(payload: object): string {
  const b64 = btoa(JSON.stringify(payload)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  return `h.${b64}.s`;
}

describe("currentRole", () => {
  afterEach(() => localStorage.removeItem("cognify_access_token"));

  it("returns the role claim from the stored JWT", () => {
    localStorage.setItem("cognify_access_token", token({ sub: "u", role: "admin" }));
    expect(currentRole()).toBe("admin");
  });

  it("returns null without a token or with garbage", () => {
    expect(currentRole()).toBeNull();
    localStorage.setItem("cognify_access_token", "not-a-jwt");
    expect(currentRole()).toBeNull();
  });
});
