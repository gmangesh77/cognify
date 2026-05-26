import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { createElement } from "react";
import { useArticle } from "./use-article";
import type { ArticleResponse } from "@/lib/api/articles";

vi.mock("@/lib/api/articles", () => ({
  fetchArticle: vi.fn(),
}));

import { fetchArticle } from "@/lib/api/articles";
const mockFetchArticle = vi.mocked(fetchArticle);

const mockArticle: ArticleResponse = {
  id: "art-001",
  title: "AI-Powered Phishing Detection Trends",
  subtitle: "How ML reshapes email security",
  body_markdown: "## Section one\n\nContent here with many words to count properly in test assertions.\n\n## Section two\n\nMore content about phishing detection trends.",
  summary: "AI-powered phishing detection reduces gaps.",
  key_claims: ["Claim one", "Claim two", "Claim three"],
  content_type: "article",
  domain: "cybersecurity",
  ai_generated: true,
  generated_at: "2026-03-21T08:00:00Z",
  seo: { title: "SEO Title", description: "desc", keywords: ["phishing"], canonical_url: null, structured_data: null },
  citations: [
    { index: 1, title: "Source 1", url: "https://example.com/1", authors: ["Author"], published_at: "2026-01-01T00:00:00Z" },
    { index: 2, title: "Source 2", url: "https://example.com/2", authors: [], published_at: null },
    { index: 3, title: "Source 3", url: "https://example.com/3", authors: [], published_at: null },
    { index: 4, title: "Source 4", url: "https://example.com/4", authors: [], published_at: null },
    { index: 5, title: "Source 5", url: "https://example.com/5", authors: [], published_at: null },
  ],
  visuals: [],
  provenance: {
    research_session_id: "rsess-a001",
    primary_model: "claude-opus-4",
    drafting_model: "claude-sonnet-4",
    embedding_model: "all-MiniLM-L6-v2",
    embedding_version: "v2.0",
  },
  authors: ["Cognify AI"],
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
  mockFetchArticle.mockResolvedValue(mockArticle);
});

describe("useArticle", () => {
  it("returns article by ID", async () => {
    const { result } = renderHook(() => useArticle("art-001"), { wrapper: createWrapper() });
    await waitFor(() => {
      expect(result.current.article).not.toBeNull();
    });
    expect(result.current.article?.title).toContain("Phishing");
  });

  it("returns null on API error", async () => {
    mockFetchArticle.mockRejectedValue(new Error("Not found"));
    const { result } = renderHook(() => useArticle("nonexistent"), { wrapper: createWrapper() });
    await waitFor(() => {
      // The hook catches errors and returns null
      expect(result.current.article).toBeNull();
    });
  });

  it("article has full detail fields", async () => {
    const { result } = renderHook(() => useArticle("art-001"), { wrapper: createWrapper() });
    await waitFor(() => {
      expect(result.current.article).not.toBeNull();
    });
    const a = result.current.article!;
    expect(a.bodyMarkdown.length).toBeGreaterThan(0);
    expect(a.citations.length).toBeGreaterThanOrEqual(5);
    expect(a.keyClaims.length).toBeGreaterThanOrEqual(3);
  });

  it("preserves image-planner placement metadata for interleaving", async () => {
    // Regression: toDetail() used to rebuild metadata with only the legacy
    // diagram fields, dropping section_index / placement_anchor / role_style.
    // That silently routed every planner visual into the cover slot.
    mockFetchArticle.mockResolvedValue({
      ...mockArticle,
      visuals: [
        {
          id: "v-cover",
          url: "/img/cover.png",
          caption: "Hero",
          alt_text: "hero",
          metadata: { role_style: "hero", placement_anchor: "cover", section_index: -1 },
        },
        {
          id: "v-1",
          url: "/img/concept.png",
          caption: "Concept",
          alt_text: "concept",
          metadata: { role_style: "concept", placement_anchor: "between_paragraphs", section_index: 1 },
        },
      ],
    });
    const { result } = renderHook(() => useArticle("art-001"), { wrapper: createWrapper() });
    await waitFor(() => {
      expect(result.current.article).not.toBeNull();
    });
    const visuals = result.current.article!.visuals;
    expect(visuals[0].metadata?.placement_anchor).toBe("cover");
    expect(visuals[1].metadata?.section_index).toBe(1);
    expect(visuals[1].metadata?.placement_anchor).toBe("between_paragraphs");
    expect(visuals[1].metadata?.role_style).toBe("concept");
  });
});
