import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "@/lib/api/articles";
import { useArticleActions } from "./use-article-actions";

vi.mock("@/lib/api/articles", () => ({
  attachVisualToArticle: vi.fn(),
  publishArticle: vi.fn(),
}));

const SPEC = {
  id: "spec-1",
  role_style: "concept",
  alt_text: "alt",
  rationale: "why",
  placement: { anchor: "before_heading", section_index: 0 },
} as never;

describe("useArticleActions", () => {
  const refetch = vi.fn().mockResolvedValue(undefined);
  const showToast = vi.fn();

  beforeEach(() => {
    vi.mocked(api.attachVisualToArticle).mockReset();
    vi.mocked(api.publishArticle).mockReset();
    refetch.mockClear();
    showToast.mockClear();
  });

  it("insertVisuals attaches hosted renders, counts base64-only ones as failed, refetches, toasts", async () => {
    vi.mocked(api.attachVisualToArticle).mockResolvedValue({} as never);
    const { result } = renderHook(() => useArticleActions({ id: "art-1", refetch, showToast }));
    await act(async () => {
      await result.current.insertVisuals([
        {
          spec: SPEC,
          render: { image_url: "https://cdn/x.png", provider: "p", model: "m" } as never,
        },
        { spec: SPEC, render: { image_url: null, image_base64: "abc" } as never },
      ]);
    });
    expect(api.attachVisualToArticle).toHaveBeenCalledTimes(1);
    expect(refetch).toHaveBeenCalledTimes(1);
    expect(showToast).toHaveBeenCalledWith("1 inserted · 1 failed (no hosted URL)", 6000);
  });

  it("publish reports one line per platform", async () => {
    vi.mocked(api.publishArticle)
      .mockResolvedValueOnce({ status: "success", external_url: "https://g/1" } as never)
      .mockRejectedValueOnce(new Error("down"));
    const { result } = renderHook(() => useArticleActions({ id: "art-1", refetch, showToast }));
    await act(async () => {
      await result.current.publish(["ghost", "medium"]);
    });
    expect(showToast).toHaveBeenCalledWith(
      "ghost: published (https://g/1) | medium: request failed",
      8000,
    );
  });
});
