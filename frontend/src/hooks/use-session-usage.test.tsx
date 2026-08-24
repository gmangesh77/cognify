import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/research");
vi.mock("@/lib/api/articles");

import * as articlesApi from "@/lib/api/articles";
import * as researchApi from "@/lib/api/research";
import { useArticleUsage, useSessionUsage } from "@/hooks/use-session-usage";
import type { UsageSummary } from "@/types/usage";

const USAGE: UsageSummary = {
  session_id: "s1",
  llm_calls: 3,
  input_tokens: 2100,
  output_tokens: 1050,
  images: 2,
  cost_usd: 0.0515,
  by_operation: [
    {
      op: "content_draft",
      llm_calls: 2,
      input_tokens: 2000,
      output_tokens: 1000,
      cost_usd: 0.021,
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
});

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useSessionUsage", () => {
  it("fetches usage for a session", async () => {
    vi.mocked(researchApi.fetchSessionUsage).mockResolvedValue(USAGE);
    const { result } = renderHook(() => useSessionUsage("s1", false), {
      wrapper,
    });
    await waitFor(() => expect(result.current.usage).toEqual(USAGE));
    expect(researchApi.fetchSessionUsage).toHaveBeenCalledWith("s1");
  });

  it("does not fetch when sessionId is null", () => {
    vi.mocked(researchApi.fetchSessionUsage).mockResolvedValue(USAGE);
    renderHook(() => useSessionUsage(null, false), { wrapper });
    expect(researchApi.fetchSessionUsage).not.toHaveBeenCalled();
  });
});

describe("useArticleUsage", () => {
  it("fetches usage for an article", async () => {
    vi.mocked(articlesApi.fetchArticleUsage).mockResolvedValue(USAGE);
    const { result } = renderHook(() => useArticleUsage("a1"), { wrapper });
    await waitFor(() => expect(result.current.usage).toEqual(USAGE));
    expect(articlesApi.fetchArticleUsage).toHaveBeenCalledWith("a1");
  });
});
