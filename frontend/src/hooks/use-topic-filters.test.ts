import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useTopicFilters } from "./use-topic-filters";
import type { RankedTopic } from "@/types/api";

const now = new Date().toISOString();
const twoDaysAgo = new Date(Date.now() - 2 * 86400000).toISOString();
const tenDaysAgo = new Date(Date.now() - 10 * 86400000).toISOString();

const topics: RankedTopic[] = [
  { title: "A", source: "reddit", domain: "cybersecurity", discovered_at: now, trend_status: "trending" } as RankedTopic,
  { title: "B", source: "hackernews", domain: "ai-ml", discovered_at: twoDaysAgo, trend_status: "new" } as RankedTopic,
  { title: "C", source: "reddit", domain: "cybersecurity", discovered_at: tenDaysAgo, trend_status: "steady" } as RankedTopic,
];

describe("useTopicFilters", () => {
  it("returns all topics with default filters", () => {
    // Default timeRange is "7d"; topic C (10 days old) is excluded
    const { result } = renderHook(() => useTopicFilters(topics));
    expect(result.current.filteredTopics).toHaveLength(2);
  });

  it("filters by source", () => {
    const { result } = renderHook(() => useTopicFilters(topics, { timeRange: "all" }));
    act(() => result.current.setFilters({ sources: ["reddit"] }));
    expect(result.current.filteredTopics).toHaveLength(2);
  });

  it("filters by domain", () => {
    const { result } = renderHook(() => useTopicFilters(topics, { timeRange: "all" }));
    act(() => result.current.setFilters({ domain: "ai-ml" }));
    expect(result.current.filteredTopics).toHaveLength(1);
    expect(result.current.filteredTopics[0].title).toBe("B");
  });

  it("filters by time range", () => {
    const { result } = renderHook(() => useTopicFilters(topics, { timeRange: "all" }));
    act(() => result.current.setFilters({ timeRange: "24h" }));
    expect(result.current.filteredTopics).toHaveLength(1);
    expect(result.current.filteredTopics[0].title).toBe("A");
  });

  it("combines filters", () => {
    const { result } = renderHook(() => useTopicFilters(topics));
    act(() => result.current.setFilters({ sources: ["reddit"], domain: "cybersecurity", timeRange: "all" }));
    expect(result.current.filteredTopics).toHaveLength(2);
  });

  it("empty sources means all sources", () => {
    const { result } = renderHook(() => useTopicFilters(topics, { timeRange: "all" }));
    act(() => result.current.setFilters({ sources: [] }));
    expect(result.current.filteredTopics).toHaveLength(3);
  });
});
