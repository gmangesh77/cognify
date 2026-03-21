import { describe, it, expect } from "vitest";
import { renderHook } from "@testing-library/react";
import { useArticle } from "./use-article";

describe("useArticle", () => {
  it("returns article by ID", () => {
    const { result } = renderHook(() => useArticle("art-001"));
    expect(result.current.article).not.toBeNull();
    expect(result.current.article?.title).toContain("Phishing");
  });

  it("returns null for unknown ID", () => {
    const { result } = renderHook(() => useArticle("nonexistent"));
    expect(result.current.article).toBeNull();
  });

  it("article has full detail fields", () => {
    const { result } = renderHook(() => useArticle("art-001"));
    const a = result.current.article!;
    expect(a.bodyMarkdown.length).toBeGreaterThan(0);
    expect(a.citations.length).toBeGreaterThanOrEqual(5);
    expect(a.keyClaims.length).toBeGreaterThanOrEqual(3);
    expect(a.workflow.length).toBeGreaterThan(0);
  });
});
