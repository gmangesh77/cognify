import { describe, it, expect, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useScanTopics } from "./use-scan-topics";

describe("useScanTopics", () => {
  it("starts with empty topics and idle scan state", () => {
    const { result } = renderHook(() => useScanTopics());
    expect(result.current.topics).toHaveLength(0);
    expect(result.current.scanState.isScanning).toBe(false);
  });

  it("sets isScanning to true during scan", async () => {
    const { result } = renderHook(() => useScanTopics());
    act(() => { result.current.startScan("cybersecurity"); });
    expect(result.current.scanState.isScanning).toBe(true);
  });

  it("populates topics after scan completes", async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useScanTopics());
    act(() => { result.current.startScan("cybersecurity"); });
    await act(async () => { vi.advanceTimersByTime(3000); });
    await waitFor(() => {
      expect(result.current.scanState.isScanning).toBe(false);
    });
    expect(result.current.topics.length).toBeGreaterThan(0);
    vi.useRealTimers();
  });

  it("tracks completed sources during scan", async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useScanTopics());
    act(() => { result.current.startScan("cybersecurity"); });
    expect(result.current.scanState.totalSources).toBe(5);
    await act(async () => { vi.advanceTimersByTime(3000); });
    await waitFor(() => {
      expect(result.current.scanState.completedSources).toBe(5);
    });
    vi.useRealTimers();
  });
});
