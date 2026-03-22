import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useScanTopics } from "./use-scan-topics";
import * as trendsApi from "@/lib/api/trends";

vi.mock("@/lib/api/trends", () => ({
  fetchTrends: vi.fn(),
  rankTopics: vi.fn(),
  persistTopics: vi.fn(),
}));

const mockFetchTrends = vi.mocked(trendsApi.fetchTrends);
const mockRankTopics = vi.mocked(trendsApi.rankTopics);
const mockPersistTopics = vi.mocked(trendsApi.persistTopics);

const mockRawTopic = {
  title: "AI Security Trends",
  description: "Latest AI security developments",
  source: "hackernews",
  external_url: "https://example.com/ai-security",
  trend_score: 85,
  discovered_at: new Date().toISOString(),
  velocity: 42,
  domain_keywords: ["ai", "security"],
};

const mockRankedTopic = {
  ...mockRawTopic,
  composite_score: 85,
  rank: 1,
  source_count: 3,
};

beforeEach(() => {
  vi.clearAllMocks();
  mockFetchTrends.mockResolvedValue({
    topics: [mockRawTopic],
    sources_queried: ["hackernews", "reddit", "google_trends", "newsapi", "arxiv"],
    source_results: {},
  });
  mockRankTopics.mockResolvedValue({
    ranked_topics: [mockRankedTopic],
    duplicates_removed: [],
    total_input: 1,
    total_after_dedup: 1,
    total_returned: 1,
  });
  mockPersistTopics.mockResolvedValue({ new_count: 1, updated_count: 0, total_persisted: 1 });
});

describe("useScanTopics", () => {
  it("starts with empty topics and idle scan state", () => {
    const { result } = renderHook(() => useScanTopics());
    expect(result.current.topics).toHaveLength(0);
    expect(result.current.scanState.isScanning).toBe(false);
  });

  it("sets isScanning to true during scan", async () => {
    // Make fetchTrends hang so we can observe the in-progress state
    mockFetchTrends.mockReturnValue(new Promise(() => {}));
    const { result } = renderHook(() => useScanTopics());
    act(() => { void result.current.startScan("cybersecurity"); });
    expect(result.current.scanState.isScanning).toBe(true);
  });

  it("populates topics after scan completes", async () => {
    const { result } = renderHook(() => useScanTopics());
    await act(async () => { await result.current.startScan("cybersecurity"); });
    await waitFor(() => {
      expect(result.current.scanState.isScanning).toBe(false);
    });
    expect(result.current.topics.length).toBeGreaterThan(0);
  });

  it("tracks completed sources after scan", async () => {
    const { result } = renderHook(() => useScanTopics());
    await act(async () => { await result.current.startScan("cybersecurity"); });
    await waitFor(() => {
      expect(result.current.scanState.completedSources).toBe(5);
    });
  });

  it("calls fetchTrends with correct domain keywords", async () => {
    const { result } = renderHook(() => useScanTopics());
    await act(async () => { await result.current.startScan("cybersecurity"); });
    expect(mockFetchTrends).toHaveBeenCalledWith({
      domain_keywords: ["cybersecurity"],
      max_results: 50,
    });
  });

  it("calls rankTopics with fetched topics", async () => {
    const { result } = renderHook(() => useScanTopics());
    await act(async () => { await result.current.startScan("cybersecurity"); });
    expect(mockRankTopics).toHaveBeenCalledWith({
      topics: [mockRawTopic],
      domain: "cybersecurity",
      domain_keywords: ["cybersecurity"],
    });
  });

  it("calls persistTopics with ranked topics after ranking", async () => {
    const { result } = renderHook(() => useScanTopics());
    await act(async () => { await result.current.startScan("cybersecurity"); });
    expect(mockPersistTopics).toHaveBeenCalledWith({
      ranked_topics: [mockRankedTopic],
      domain: "cybersecurity",
    });
  });

  it("shows topics even when persistTopics fails", async () => {
    mockPersistTopics.mockRejectedValue(new Error("DB unavailable"));
    const consoleSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const { result } = renderHook(() => useScanTopics());
    await act(async () => { await result.current.startScan("cybersecurity"); });
    await waitFor(() => {
      expect(result.current.topics.length).toBeGreaterThan(0);
    });
    expect(consoleSpy).toHaveBeenCalledWith(
      "Topic persistence failed — results shown but not saved"
    );
    consoleSpy.mockRestore();
  });

  it("assigns trend_status to each topic", async () => {
    const { result } = renderHook(() => useScanTopics());
    await act(async () => { await result.current.startScan("cybersecurity"); });
    await waitFor(() => {
      expect(result.current.topics.length).toBeGreaterThan(0);
    });
    for (const topic of result.current.topics) {
      expect(["trending", "rising", "new", "steady"]).toContain(topic.trend_status);
    }
  });
});
