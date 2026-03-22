import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { createElement } from "react";
import { useArticleList } from "./use-article-list";
import type { PaginatedArticles } from "@/lib/api/articles";

vi.mock("@/lib/api/articles", () => ({
  fetchArticles: vi.fn(),
}));

import { fetchArticles } from "@/lib/api/articles";
const mockFetchArticles = vi.mocked(fetchArticles);

const mockResponse: PaginatedArticles = {
  items: [
    {
      id: "art-001",
      title: "AI-Powered Phishing Detection Trends",
      subtitle: null,
      body_markdown: "Word one two three four five six seven eight nine ten",
      summary: "AI phishing detection summary",
      key_claims: ["claim1"],
      content_type: "article",
      domain: "cybersecurity",
      ai_generated: true,
      generated_at: "2026-03-21T08:00:00Z",
      seo: { title: "SEO Title", description: "desc", keywords: [], canonical_url: null, structured_data: null },
      citations: [{ index: 1, title: "Source", url: "https://example.com", authors: [], published_at: null }],
      visuals: [],
      provenance: {
        research_session_id: "rsess-001",
        primary_model: "claude-opus-4",
        drafting_model: "claude-sonnet-4",
        embedding_model: "all-MiniLM-L6-v2",
        embedding_version: "v2.0",
      },
      authors: ["Cognify AI"],
    },
  ],
  total: 1,
  page: 1,
  size: 20,
};

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mockFetchArticles.mockResolvedValue(mockResponse);
});

describe("useArticleList", () => {
  it("returns articles from API", async () => {
    const { result } = renderHook(() => useArticleList(), { wrapper: createWrapper() });
    await waitFor(() => {
      expect(result.current.articles.length).toBeGreaterThan(0);
    });
  });

  it("each article has required fields", async () => {
    const { result } = renderHook(() => useArticleList(), { wrapper: createWrapper() });
    await waitFor(() => {
      expect(result.current.articles.length).toBeGreaterThan(0);
    });
    const article = result.current.articles[0];
    expect(article.id).toBeDefined();
    expect(article.title).toBeDefined();
    expect(article.summary).toBeDefined();
    expect(article.domain).toBeDefined();
    expect(article.status).toBeDefined();
    expect(article.wordCount).toBeGreaterThan(0);
  });

  it("returns empty array on API error", async () => {
    mockFetchArticles.mockRejectedValue(new Error("Network error"));
    const { result } = renderHook(() => useArticleList(), { wrapper: createWrapper() });
    await waitFor(() => {
      expect(result.current.articles).toEqual([]);
    });
  });
});
