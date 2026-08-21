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

  it("drops a stale response when a newer run() started", async () => {
    let resolveFirst!: (v: typeof RESPONSE) => void;
    vi.mocked(api.regenerateSection)
      .mockImplementationOnce(
        () => new Promise((resolve) => (resolveFirst = resolve)),
      )
      .mockResolvedValueOnce({ ...RESPONSE, version_id: "v2" });
    const { result } = renderHook(() => useSectionRegenerate());
    act(() => {
      void result.current.run({ article_id: "a", section_index: 0 });
    });
    await act(async () => {
      await result.current.run({ article_id: "a", section_index: 0 });
    });
    await waitFor(() => expect(result.current.result?.version_id).toBe("v2"));
    await act(async () => {
      resolveFirst({ ...RESPONSE, version_id: "v1" });
    });
    expect(result.current.result?.version_id).toBe("v2");
  });

  it("maps 409/429/503 to readable messages", async () => {
    for (const [status, text] of [
      [409, "no stored outline"],
      [429, "Too many regenerations"],
      [503, "not configured"],
    ] as const) {
      vi.mocked(api.regenerateSection).mockRejectedValueOnce(
        Object.assign(new Error(`Request failed with status code ${status}`), {
          response: { status },
        }),
      );
      const { result } = renderHook(() => useSectionRegenerate());
      await act(async () => {
        await result.current.run({ article_id: "a", section_index: 0 });
      });
      expect(result.current.error).toContain(text);
    }
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
