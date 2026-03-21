import { describe, it, expect } from "vitest";
import { renderHook } from "@testing-library/react";
import { useArticleList } from "./use-article-list";

describe("useArticleList", () => {
  it("returns mock articles", () => {
    const { result } = renderHook(() => useArticleList());
    expect(result.current.articles.length).toBeGreaterThan(0);
  });

  it("each article has required fields", () => {
    const { result } = renderHook(() => useArticleList());
    const article = result.current.articles[0];
    expect(article.id).toBeDefined();
    expect(article.title).toBeDefined();
    expect(article.summary).toBeDefined();
    expect(article.domain).toBeDefined();
    expect(article.status).toBeDefined();
    expect(article.wordCount).toBeGreaterThan(0);
  });
});
