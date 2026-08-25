import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/articles");

import * as articlesApi from "@/lib/api/articles";
import { useArticleMetadata } from "@/hooks/use-article-metadata";
import type { ArticleMetadataResult } from "@/types/articles";

const RESULT: ArticleMetadataResult = {
  id: "a1",
  title: "New title",
  subtitle: null,
  seo: { title: "Seo", description: "Desc", keywords: ["k"] },
  warnings: [{ field: "seo_title", message: "seo_title is 3 chars; 50-60 recommended" }],
};

let client: QueryClient;

beforeEach(() => {
  vi.clearAllMocks();
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
});

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useArticleMetadata", () => {
  it("saves a patch and invalidates the article query", async () => {
    vi.mocked(articlesApi.patchArticleMetadata).mockResolvedValue(RESULT);
    const invalidate = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useArticleMetadata("a1"), { wrapper });
    const saved = await result.current.save({ title: "New title" });
    expect(saved.warnings).toHaveLength(1);
    expect(articlesApi.patchArticleMetadata).toHaveBeenCalledWith("a1", {
      title: "New title",
    });
    await waitFor(() =>
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ["article", "a1"] }),
    );
    // AUTHOR-007: status edits also refresh the list + dashboard caches.
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["article-list"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["articles"] });
  });

  it("regenerates a single seo field", async () => {
    vi.mocked(articlesApi.regenerateSeoField).mockResolvedValue({
      field: "seo_title",
      value: "Proposed title",
      warnings: [],
    });
    const { result } = renderHook(() => useArticleMetadata("a1"), { wrapper });
    const regen = await result.current.regenerate("seo_title");
    expect(regen.value).toBe("Proposed title");
    expect(articlesApi.regenerateSeoField).toHaveBeenCalledWith("a1", "seo_title");
  });
});
