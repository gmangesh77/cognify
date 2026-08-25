import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/research");

import * as researchApi from "@/lib/api/research";
import { useResumableSessions } from "@/hooks/use-resumable-sessions";
import type { PaginatedResearchSessions } from "@/types/research";

function page(items: object[]): PaginatedResearchSessions {
  return {
    items,
    total: items.length,
    page: 1,
    size: 10,
  } as PaginatedResearchSessions;
}

function summary(id: string, status: string): object {
  return {
    session_id: id,
    topic_id: "t1",
    status,
    round_count: 1,
    findings_count: 0,
    sources_count: 0,
    embeddings_count: 0,
    topic_title: `Topic ${id}`,
    duration_seconds: null,
    started_at: "2026-08-25T08:00:00Z",
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useResumableSessions", () => {
  it("merges and dedupes the three resumable filters", async () => {
    vi.mocked(researchApi.fetchSessions).mockImplementation(async (status) => {
      if (status === "generating_article") return page([summary("s1", "generating_article")]);
      if (status === "awaiting_outline_review") return page([summary("s2", "awaiting_outline_review")]);
      if (status === "failed")
        return page([summary("s3", "article_failed"), summary("s1", "generating_article")]);
      return page([]);
    });
    const { result } = renderHook(() => useResumableSessions(), { wrapper });
    await waitFor(() => expect(result.current.sessions).toHaveLength(3));
    expect(result.current.sessions.map((s) => s.session_id).sort()).toEqual([
      "s1",
      "s2",
      "s3",
    ]);
  });

  it("returns empty on API errors", async () => {
    vi.mocked(researchApi.fetchSessions).mockRejectedValue(new Error("boom"));
    const { result } = renderHook(() => useResumableSessions(), { wrapper });
    await waitFor(() => expect(result.current.sessions).toEqual([]));
  });
});
