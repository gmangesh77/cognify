import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/articles", () => ({
  fetchArticles: vi.fn(),
}));
vi.mock("@/lib/api/research", () => ({
  fetchSessions: vi.fn(),
}));
vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));

import { fetchArticles } from "@/lib/api/articles";
import { fetchSessions } from "@/lib/api/research";
import ArticlesPage from "./page";

const ARTICLE = {
  id: "art-1",
  title: "Filterable Article",
  subtitle: null,
  body_markdown: "one two three",
  summary: "Summary",
  key_claims: [],
  content_type: "article",
  domain: "testing",
  ai_generated: true,
  generated_at: "2026-08-25T08:00:00Z",
  seo: { title: "t", description: "d", keywords: [], canonical_url: null, structured_data: null },
  citations: [],
  visuals: [],
  provenance: {
    research_session_id: "r1",
    primary_model: "m",
    drafting_model: "m",
    embedding_model: "e",
    embedding_version: "v1",
  },
  authors: ["Cognify"],
  status: "approved",
};

function sessionsPage(items: object[]) {
  return { items, total: items.length, page: 1, size: 10 };
}

const FAILED_SESSION = {
  session_id: "sess-9",
  topic_id: "t1",
  status: "article_failed",
  round_count: 1,
  findings_count: 0,
  sources_count: 0,
  embeddings_count: 0,
  topic_title: "Broken run",
  duration_seconds: null,
  started_at: "2026-08-25T08:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(fetchArticles).mockResolvedValue({
    items: [ARTICLE],
    total: 1,
    page: 1,
    size: 20,
  } as never);
  vi.mocked(fetchSessions).mockImplementation(async (status) =>
    (status === "failed" ? sessionsPage([FAILED_SESSION]) : sessionsPage([])) as never,
  );
});

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ArticlesPage />
    </QueryClientProvider>,
  );
}

describe("ArticlesPage (AUTHOR-007)", () => {
  it("renders articles with filter pills and the resume strip", async () => {
    renderPage();
    expect(await screen.findByText("Filterable Article")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approved" })).toBeInTheDocument();
    expect(await screen.findByText("Broken run")).toBeInTheDocument();
    const resume = screen.getByRole("link", { name: /resume/i });
    expect(resume).toHaveAttribute("href", "/research/sess-9");
  });

  it("clicking a pill refetches with the status filter", async () => {
    renderPage();
    await screen.findByText("Filterable Article");
    fireEvent.click(screen.getByRole("button", { name: "Draft" }));
    await waitFor(() =>
      expect(fetchArticles).toHaveBeenCalledWith(1, 20, "draft"),
    );
  });

  it("renders no strip when nothing is resumable", async () => {
    vi.mocked(fetchSessions).mockResolvedValue(sessionsPage([]) as never);
    renderPage();
    await screen.findByText("Filterable Article");
    expect(screen.queryByText(/resume/i)).toBeNull();
  });
});
