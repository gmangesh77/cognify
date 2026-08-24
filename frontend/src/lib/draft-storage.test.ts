import { beforeEach, describe, expect, it } from "vitest";

import { clearDraft, loadDraft, saveDraft } from "./draft-storage";

beforeEach(() => {
  localStorage.clear();
});

describe("draft-storage", () => {
  it("round-trips a draft under the namespaced key", () => {
    saveDraft("art1:2", "## Edited\n\nBody");
    expect(localStorage.getItem("cognify:draft:art1:2")).toBe("## Edited\n\nBody");
    expect(loadDraft("art1:2")).toBe("## Edited\n\nBody");
  });

  it("returns null for a missing draft", () => {
    expect(loadDraft("art1:9")).toBeNull();
  });

  it("clears a stored draft", () => {
    saveDraft("art1:2", "text");
    clearDraft("art1:2");
    expect(loadDraft("art1:2")).toBeNull();
    expect(localStorage.getItem("cognify:draft:art1:2")).toBeNull();
  });
});
