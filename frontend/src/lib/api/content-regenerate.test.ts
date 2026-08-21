import { describe, expect, it, vi, beforeEach } from "vitest";
import { apiClient } from "@/lib/api/client";
import { regenerateSection } from "@/lib/api/content";
import { extractAnchorViolations } from "@/lib/api/anchorViolations";

vi.mock("@/lib/api/client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

const RESPONSE = {
  section_id: "a:0",
  section_index: 0,
  markdown: "## H\n\nnew",
  diff: [],
  version_id: "v1",
  model: "claude",
  word_count: 1,
  tokens_input: 10,
  tokens_output: 5,
  instruction: "tighter",
};

describe("regenerateSection", () => {
  beforeEach(() => vi.clearAllMocks());

  it("POSTs to /content/section-regenerate and returns data", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: RESPONSE });
    const out = await regenerateSection({
      article_id: "a",
      section_index: 0,
      instruction: "tighter",
    });
    expect(apiClient.post).toHaveBeenCalledWith("/content/section-regenerate", {
      article_id: "a",
      section_index: 0,
      instruction: "tighter",
    });
    expect(out).toEqual(RESPONSE);
  });
});

describe("extractAnchorViolations", () => {
  it("returns violations from a 422 detail payload", () => {
    const err = {
      response: {
        status: 422,
        data: {
          detail: {
            violations: [
              { kind: "spec_id", value: "s", spec_id: "s", message: "m" },
            ],
          },
        },
      },
    };
    expect(extractAnchorViolations(err)).toHaveLength(1);
  });

  it("returns [] for anything else", () => {
    expect(extractAnchorViolations({ response: { status: 500 } })).toEqual([]);
    expect(extractAnchorViolations(new Error("x"))).toEqual([]);
  });
});
