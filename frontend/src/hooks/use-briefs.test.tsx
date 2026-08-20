import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useBriefs } from "./use-briefs";
import * as api from "@/lib/api/briefs";
import type { Brief } from "@/types/brief";

vi.mock("@/lib/api/briefs");

const brief: Brief = { id: "b1", owner_id: "u", name: "A", keywords: [], content_type: "article" as const,
  length_target: "medium" as const, structural_diagram_mode: "illustration" as const,
  require_outline_approval: false, created_at: "", updated_at: "" };

function wrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("useBriefs", () => {
  beforeEach(() => vi.clearAllMocks());

  it("loads briefs", async () => {
    vi.mocked(api.fetchBriefs).mockResolvedValue([brief]);
    const { result } = renderHook(() => useBriefs(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.briefs).toEqual([brief]);
  });

  it("create refetches the list", async () => {
    vi.mocked(api.fetchBriefs).mockResolvedValueOnce([]).mockResolvedValueOnce([brief]);
    vi.mocked(api.createBrief).mockResolvedValue(brief);
    const { result } = renderHook(() => useBriefs(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    await act(async () => { await result.current.create({ ...brief }); });
    await waitFor(() => expect(result.current.briefs).toEqual([brief]));
  });

  it("surfaces a load error", async () => {
    vi.mocked(api.fetchBriefs).mockRejectedValue(new Error("boom"));
    const { result } = renderHook(() => useBriefs(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.error).toBe("boom"));
  });
});
