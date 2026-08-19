import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

const consume = vi.fn();
vi.mock("@/lib/sse/consume-sse", () => ({ consumeSse: (...a: unknown[]) => consume(...a) }));
vi.mock("@/lib/api/client", () => ({
  getAccessToken: () => "T",
  apiClient: { defaults: { baseURL: "http://api/api/v1" } },
}));

import { useSessionEvents } from "./use-session-events";

beforeEach(() => {
  consume.mockReset();
});

describe("useSessionEvents", () => {
  it("applies snapshot, progress and done events", async () => {
    let emit!: (t: string, d: unknown) => void;
    consume.mockImplementation(async (_url: string, o: { onEvent: typeof emit }) => {
      emit = o.onEvent;
      await new Promise(() => {});
    });
    const { result } = renderHook(() => useSessionEvents("s1"));
    await waitFor(() => expect(consume).toHaveBeenCalled());
    act(() =>
      emit("snapshot", {
        type: "snapshot",
        session_id: "s1",
        status: "researching",
        step: null,
        ts: "",
        data: {
          steps: [
            {
              id: "a",
              step_name: "plan_research",
              status: "complete",
              started_at: "",
              completed_at: null,
              duration_ms: 5,
              output_data: {},
            },
          ],
        },
      }),
    );
    expect(result.current.steps).toHaveLength(1);
    act(() =>
      emit("step_started", {
        type: "step_started",
        session_id: "s1",
        status: "running",
        step: "content_draft",
        ts: "",
        data: { step_id: "b" },
      }),
    );
    act(() =>
      emit("step_progress", {
        type: "step_progress",
        session_id: "s1",
        status: "running",
        step: "content_draft",
        ts: "",
        data: { step_id: "b", sections_done: 2, sections_total: 5, current_section: "Intro" },
      }),
    );
    expect(result.current.sections).toEqual({ done: 2, total: 5, current: "Intro" });
    act(() =>
      emit("done", {
        type: "done",
        session_id: "s1",
        status: "article_complete",
        step: null,
        ts: "",
        data: {},
      }),
    );
    expect(result.current.status).toBe("article_complete");
    expect(result.current.connection).toBe("closed");
  });

  it("reports error state when the stream fails", async () => {
    consume.mockRejectedValue(new Error("SSE request failed: 503"));
    const { result } = renderHook(() =>
      useSessionEvents("s1", { maxAttempts: 1, baseDelayMs: 0 }),
    );
    await waitFor(() => expect(result.current.connection).toBe("error"));
    expect(result.current.error).toMatch(/503/);
  });

  it("shows reconnecting (not error) while retries remain under the attempt cap", async () => {
    let callCount = 0;
    consume.mockImplementation(async () => {
      callCount += 1;
      if (callCount === 1) throw new Error("SSE request failed: 503");
      // second attempt: hang so state settles on "reconnecting" instead of
      // racing forward to a second failure / "error".
      await new Promise(() => {});
    });
    const { result } = renderHook(() =>
      useSessionEvents("s1", { maxAttempts: 2, baseDelayMs: 0 }),
    );
    await waitFor(() => expect(result.current.connection).toBe("reconnecting"));
    expect(result.current.error).toMatch(/503/);
    expect(result.current.connection).not.toBe("error");
  });

  it("does nothing for null session id", () => {
    renderHook(() => useSessionEvents(null));
    expect(consume).not.toHaveBeenCalled();
  });

  it("reconnects when the stream ends without any events (server closed early)", async () => {
    consume.mockImplementation(async () => {
      // resolves immediately, no events emitted — simulates a dropped connection
    });
    const { result } = renderHook(() =>
      useSessionEvents("s1", { maxAttempts: 5, baseDelayMs: 10000 }),
    );
    await waitFor(() => expect(result.current.connection).toBe("reconnecting"));
  });

  it("reconnects when done arrives with a non-terminal status (e.g. server max_seconds timeout)", async () => {
    consume.mockImplementation(
      async (_url: string, o: { onEvent: (t: string, d: unknown) => void }) => {
        o.onEvent("done", {
          type: "done",
          session_id: "s1",
          status: "researching",
          step: null,
          ts: "",
          data: { reason: "timeout" },
        });
      },
    );
    const { result } = renderHook(() =>
      useSessionEvents("s1", { maxAttempts: 5, baseDelayMs: 10000 }),
    );
    await waitFor(() => expect(result.current.connection).toBe("reconnecting"));
  });

  it("closes with no reconnect when done arrives with a terminal status", async () => {
    consume.mockImplementation(
      async (_url: string, o: { onEvent: (t: string, d: unknown) => void }) => {
        o.onEvent("done", {
          type: "done",
          session_id: "s1",
          status: "article_complete",
          step: null,
          ts: "",
          data: {},
        });
      },
    );
    const { result } = renderHook(() => useSessionEvents("s1"));
    await waitFor(() => expect(result.current.connection).toBe("closed"));
    expect(consume).toHaveBeenCalledTimes(1);
  });

  it("resets the retry counter once the stream goes live again, so later drops don't hit the hard error state", async () => {
    let callCount = 0;
    consume.mockImplementation(
      async (_url: string, o: { onEvent: (t: string, d: unknown) => void }) => {
        callCount += 1;
        if (callCount === 1) {
          // first connection: fails outright (attempt 1/2)
          throw new Error("SSE request failed: 503");
        }
        if (callCount === 2) {
          // second connection: a real event arrives (resets attempt counter),
          // then the stream ends without a terminal done (attempt 1/2 again,
          // not 2/2 — proving the counter was reset).
          o.onEvent("status_changed", {
            type: "status_changed",
            session_id: "s1",
            status: "researching",
            step: null,
            ts: "",
            data: {},
          });
          return;
        }
        // third connection onward: hang so state settles as "reconnecting"
        await new Promise(() => {});
      },
    );
    const { result } = renderHook(() =>
      useSessionEvents("s1", { maxAttempts: 2, baseDelayMs: 0 }),
    );
    await waitFor(() => expect(callCount).toBeGreaterThanOrEqual(3));
    expect(result.current.connection).toBe("reconnecting");
    expect(result.current.connection).not.toBe("error");
  });
});
