import { describe, expect, it, vi, beforeEach } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useLinkedInRepurpose } from "./use-linkedin-repurpose";
import * as api from "@/lib/api/articles";

vi.mock("@/lib/api/articles", () => ({
  repurposeLinkedin: vi.fn(),
  publishLinkedinPost: vi.fn(),
}));

const DRAFT = {
  article_id: "a1",
  hook: "hook line",
  beats: ["b1", "b2", "b3"],
  cta: "read more",
  hashtags: ["#ai"],
  text: "hook line\n\nb1\n\nb2\n\nb3\n\nread more\n\n#ai",
  char_count: 40,
  slop_score: 92,
  slop_rating: "Human",
  model: "claude-sonnet-4-6",
  truncated: false,
};

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient();
  return (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

describe("useLinkedInRepurpose", () => {
  const showToast = vi.fn();

  beforeEach(() => {
    vi.mocked(api.repurposeLinkedin).mockReset();
    vi.mocked(api.publishLinkedinPost).mockReset();
    showToast.mockReset();
  });

  it("starts idle with empty text", () => {
    const { result } = renderHook(
      () => useLinkedInRepurpose({ articleId: "a1", showToast }),
      { wrapper },
    );
    expect(result.current.draft).toBeNull();
    expect(result.current.text).toBe("");
    expect(result.current.busy).toBe(false);
    expect(result.current.publishedUrl).toBeNull();
  });

  it("generate() sets text from draft.text", async () => {
    vi.mocked(api.repurposeLinkedin).mockResolvedValue(DRAFT);
    const { result } = renderHook(
      () => useLinkedInRepurpose({ articleId: "a1", showToast }),
      { wrapper },
    );
    await act(async () => {
      await result.current.generate();
    });
    await waitFor(() => expect(result.current.draft).toEqual(DRAFT));
    expect(result.current.text).toBe(DRAFT.text);
    expect(result.current.error).toBeNull();
  });

  it("passes the instruction through to the API", async () => {
    vi.mocked(api.repurposeLinkedin).mockResolvedValue(DRAFT);
    const { result } = renderHook(
      () => useLinkedInRepurpose({ articleId: "a1", showToast }),
      { wrapper },
    );
    await act(async () => {
      await result.current.generate("punchier");
    });
    expect(api.repurposeLinkedin).toHaveBeenCalledWith("a1", "punchier");
  });

  it("publish() uses the CURRENT edited text, not draft.text", async () => {
    vi.mocked(api.repurposeLinkedin).mockResolvedValue(DRAFT);
    vi.mocked(api.publishLinkedinPost).mockResolvedValue({
      article_id: "a1",
      platform: "linkedin_post",
      status: "success",
      external_id: "urn:li:share:1",
      external_url: "https://linkedin.com/feed/update/1",
      published_at: "2026-09-02T00:00:00Z",
      error_message: null,
    });
    const { result } = renderHook(
      () => useLinkedInRepurpose({ articleId: "a1", showToast }),
      { wrapper },
    );
    await act(async () => {
      await result.current.generate();
    });
    act(() => result.current.setText("edited text"));
    await act(async () => {
      await result.current.publish();
    });
    expect(api.publishLinkedinPost).toHaveBeenCalledWith("a1", "edited text");
    expect(result.current.publishedUrl).toBe(
      "https://linkedin.com/feed/update/1",
    );
    expect(showToast).toHaveBeenCalledWith(
      expect.stringMatching(/posted/i),
    );
  });

  it("publish 503 with code platform_unavailable maps to the not-connected message", async () => {
    vi.mocked(api.repurposeLinkedin).mockResolvedValue(DRAFT);
    vi.mocked(api.publishLinkedinPost).mockRejectedValue({
      response: {
        status: 503,
        data: { error: { code: "platform_unavailable", message: "LinkedIn is not connected" } },
      },
    });
    const { result } = renderHook(
      () => useLinkedInRepurpose({ articleId: "a1", showToast }),
      { wrapper },
    );
    await act(async () => {
      await result.current.generate();
    });
    await act(async () => {
      await result.current.publish();
    });
    expect(result.current.error).toMatch(/not connected/i);
    expect(result.current.publishedUrl).toBeNull();
  });

  it("repurpose 503 (LLM unavailable) does NOT map to the not-connected message", async () => {
    vi.mocked(api.repurposeLinkedin).mockRejectedValue({
      response: {
        status: 503,
        data: { error: { code: "service_unavailable", message: "LLM not configured" } },
      },
    });
    const { result } = renderHook(
      () => useLinkedInRepurpose({ articleId: "a1", showToast }),
      { wrapper },
    );
    await act(async () => {
      await result.current.generate();
    });
    expect(result.current.error).not.toMatch(/not connected/i);
  });

  it("a publish 503 WITHOUT the platform_unavailable code surfaces a generic error", async () => {
    vi.mocked(api.repurposeLinkedin).mockResolvedValue(DRAFT);
    vi.mocked(api.publishLinkedinPost).mockRejectedValue({
      response: { status: 503, data: { error: { code: "service_unavailable" } } },
    });
    const { result } = renderHook(
      () => useLinkedInRepurpose({ articleId: "a1", showToast }),
      { wrapper },
    );
    await act(async () => {
      await result.current.generate();
    });
    await act(async () => {
      await result.current.publish();
    });
    expect(result.current.error).not.toMatch(/not connected/i);
  });
});
