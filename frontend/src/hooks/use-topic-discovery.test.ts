import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useTopicDiscovery } from "./use-topic-discovery";
import type { RankedTopic } from "@/types/api";

describe("useTopicDiscovery", () => {
  it("starts with null modalTopic", () => {
    const { result } = renderHook(() => useTopicDiscovery());
    expect(result.current.modalTopic).toBeNull();
  });

  it("opens and closes modal", () => {
    const { result } = renderHook(() => useTopicDiscovery());
    const fakeTopic: RankedTopic = {
      title: "Test", description: "", source: "reddit", external_url: "",
      trend_score: 50, discovered_at: new Date().toISOString(), velocity: 10,
      domain_keywords: [], composite_score: 50, rank: 1, source_count: 1,
      domain: "cybersecurity", trend_status: "steady",
    };
    act(() => result.current.openModal(fakeTopic));
    expect(result.current.modalTopic).toEqual(fakeTopic);
    act(() => result.current.closeModal());
    expect(result.current.modalTopic).toBeNull();
  });

  it("exposes scan state from useScanTopics", () => {
    const { result } = renderHook(() => useTopicDiscovery());
    expect(result.current.scanState.isScanning).toBe(false);
  });

  it("exposes filter state", () => {
    const { result } = renderHook(() => useTopicDiscovery());
    expect(result.current.filters.timeRange).toBe("7d");
  });

  it("exposes pagination state", () => {
    const { result } = renderHook(() => useTopicDiscovery());
    expect(result.current.page).toBe(1);
  });
});
