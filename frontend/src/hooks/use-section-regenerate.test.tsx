import { describe, expect, it, vi, beforeEach } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { useSectionRegenerate } from "./use-section-regenerate";
import * as api from "@/lib/api/content";

vi.mock("@/lib/api/content", () => ({ regenerateSection: vi.fn() }));

const RESPONSE = {
  section_id: "a:0",
  section_index: 0,
  markdown: "## H\n\nnew text",
  diff: [{ kind: "replace" as const, before: "old", after: "new" }],
  version_id: "v1",
  model: "claude",
  word_count: 2,
  tokens_input: null,
  tokens_output: null,
  instruction: null,
};

describe("useSectionRegenerate", () => {
  beforeEach(() => vi.mocked(api.regenerateSection).mockReset());

  it("starts idle", () => {
    const { result } = renderHook(() => useSectionRegenerate());
    expect(result.current.busy).toBe(false);
    expect(result.current.result).toBeNull();
  });

  it("stores the result after run()", async () => {
    vi.mocked(api.regenerateSection).mockResolvedValue(RESPONSE);
    const { result } = renderHook(() => useSectionRegenerate());
    await act(async () => {
      await result.current.run({ article_id: "a", section_index: 0 });
    });
    await waitFor(() => expect(result.current.result).toEqual(RESPONSE));
    expect(result.current.busy).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("maps a 422 into violations and a generic error otherwise", async () => {
    vi.mocked(api.regenerateSection).mockRejectedValueOnce({
      response: {
        status: 422,
        data: {
          detail: {
            violations: [
              { kind: "spec_id", value: "s", spec_id: "s", message: "dropped" },
            ],
          },
        },
      },
    });
    const { result } = renderHook(() => useSectionRegenerate());
    await act(async () => {
      await result.current.run({ article_id: "a", section_index: 0 });
    });
    expect(result.current.violations).toHaveLength(1);
    expect(result.current.error).toMatch(/anchor/i);

    vi.mocked(api.regenerateSection).mockRejectedValueOnce(new Error("boom"));
    await act(async () => {
      await result.current.run({ article_id: "a", section_index: 0 });
    });
    expect(result.current.violations).toEqual([]);
    expect(result.current.error).toBe("boom");
  });

  it("reset() clears everything", async () => {
    vi.mocked(api.regenerateSection).mockResolvedValue(RESPONSE);
    const { result } = renderHook(() => useSectionRegenerate());
    await act(async () => {
      await result.current.run({ article_id: "a", section_index: 0 });
    });
    act(() => result.current.reset());
    expect(result.current.result).toBeNull();
    expect(result.current.error).toBeNull();
  });
});
