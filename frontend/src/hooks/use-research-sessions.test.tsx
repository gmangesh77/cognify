import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useResearchSessions, useResearchSession } from "./use-research-sessions";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe("useResearchSessions", () => {
  it("returns paginated sessions", async () => {
    const { result } = renderHook(() => useResearchSessions(), {
      wrapper: createWrapper(),
    });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data!.items.length).toBeGreaterThan(0);
    expect(result.current.data!.total).toBe(8);
    expect(result.current.data!.page).toBe(1);
  });

  it("filters by status", async () => {
    const { result } = renderHook(() => useResearchSessions("complete"), {
      wrapper: createWrapper(),
    });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data!.items.every((s) => s.status === "complete")).toBe(true);
  });

  it("respects page and size params", async () => {
    const { result } = renderHook(() => useResearchSessions(undefined, 1, 3), {
      wrapper: createWrapper(),
    });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data!.items.length).toBe(3);
    expect(result.current.data!.size).toBe(3);
  });
});

describe("useResearchSession", () => {
  it("returns null when sessionId is null", () => {
    const { result } = renderHook(() => useResearchSession(null), {
      wrapper: createWrapper(),
    });
    expect(result.current.data).toBeUndefined();
  });

  it("returns session detail with steps", async () => {
    const { result } = renderHook(() => useResearchSession("sess-001"), {
      wrapper: createWrapper(),
    });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data!.steps.length).toBe(5);
    expect(result.current.data!.session_id).toBe("sess-001");
  });
});
