import { describe, expect, it, vi, beforeEach } from "vitest";
import { apiClient } from "@/lib/api/client";
import { repurposeLinkedin, publishLinkedinPost } from "@/lib/api/articles";

vi.mock("@/lib/api/client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

const DRAFT = {
  article_id: "a1",
  hook: "hook",
  beats: ["b1", "b2", "b3"],
  cta: "cta",
  hashtags: ["#ai"],
  text: "hook\n\nb1\n\nb2\n\nb3\n\ncta\n\n#ai",
  char_count: 30,
  slop_score: 90,
  slop_rating: "Human",
  model: "claude-sonnet-4-6",
  truncated: false,
};

describe("repurposeLinkedin", () => {
  beforeEach(() => vi.clearAllMocks());

  it("POSTs without an instruction", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: DRAFT });
    const out = await repurposeLinkedin("a1");
    expect(apiClient.post).toHaveBeenCalledWith(
      "/articles/a1/repurpose/linkedin",
      {},
    );
    expect(out).toEqual(DRAFT);
  });

  it("POSTs with an instruction", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: DRAFT });
    await repurposeLinkedin("a1", "make it punchier");
    expect(apiClient.post).toHaveBeenCalledWith(
      "/articles/a1/repurpose/linkedin",
      { instruction: "make it punchier" },
    );
  });
});

describe("publishLinkedinPost", () => {
  beforeEach(() => vi.clearAllMocks());

  it("POSTs the edited text", async () => {
    const result = {
      article_id: "a1",
      platform: "linkedin_post",
      status: "success",
      external_id: "urn:li:share:1",
      external_url: "https://linkedin.com/feed/update/1",
      published_at: "2026-09-02T00:00:00Z",
      error_message: null,
    };
    vi.mocked(apiClient.post).mockResolvedValue({ data: result });
    const out = await publishLinkedinPost("a1", "final text");
    expect(apiClient.post).toHaveBeenCalledWith(
      "/articles/a1/repurpose/linkedin/publish",
      { text: "final text" },
    );
    expect(out).toEqual(result);
  });
});
