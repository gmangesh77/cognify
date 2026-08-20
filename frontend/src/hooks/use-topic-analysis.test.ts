import { describe, it, expect, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useTopicAnalysis } from "./use-topic-analysis";

vi.mock("@/lib/api/trends", () => ({
  analyzeTopic: vi.fn().mockResolvedValue({
    description: "LLM generated description",
    domain: "cybersecurity",
    keywords: ["phishing", "ML detection"],
    target_audience: "security engineers",
    content_tone: "technical-authoritative",
    preferred_angle: "practical defender playbook",
  }),
}));

describe("useTopicAnalysis", () => {
  it("applies two synchronous updateField calls without dropping either value", async () => {
    // Regression guard for the stale-closure bug: applyBrief (in
    // use-generate-modal-state) calls updateField several times in one
    // synchronous handler when a saved brief is picked. updateField used to
    // read a captured `analysis` snapshot instead of the pending state, so
    // only the last of several sequential calls in a batch survived.
    const { result } = renderHook(() => useTopicAnalysis());

    await act(async () => {
      await result.current.analyze("Zero Trust");
    });
    await waitFor(() => expect(result.current.analysis).not.toBeNull());

    act(() => {
      result.current.updateField("target_audience", "CISOs");
      result.current.updateField("content_tone", "analytical");
    });

    expect(result.current.analysis?.target_audience).toBe("CISOs");
    expect(result.current.analysis?.content_tone).toBe("analytical");
  });
});
