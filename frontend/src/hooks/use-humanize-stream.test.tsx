import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const consume = vi.fn();
vi.mock("@/lib/sse/consume-sse", () => ({ consumeSse: (...a: unknown[]) => consume(...a) }));
vi.mock("@/lib/api/client", () => ({
  getAccessToken: () => "T",
  apiClient: { defaults: { baseURL: "http://api/api/v1" } },
}));

import { useHumanizeStream } from "./use-humanize-stream";

const DONE = {
  original: "A. Old.",
  rewritten: "A. New.",
  diff: [],
  passes: 2,
  llm_called: true,
  model: "claude",
  score_before: 30,
  score_after: 85,
  segments: [
    { id: "s0", kind: "equal" as const, before: "A. ", after: "A. ", ops: [] },
    { id: "s1", kind: "change" as const, before: "Old.", after: "New.", ops: [] },
  ],
};

const PASS0 = {
  index: 0,
  name: "mechanical" as const,
  score_before: 30,
  score_after: 32,
  rating: "x",
  changed: false,
  model: null,
};
const PASS1 = { ...PASS0, index: 1, name: "llm" as const, score_after: 85, changed: true, model: "claude" };

let emit!: (t: string, d: unknown) => void;
let finish!: () => void;

beforeEach(() => {
  consume.mockReset();
  consume.mockImplementation(async (_url: string, o: { onEvent: typeof emit }) => {
    emit = o.onEvent;
    await new Promise<void>((resolve) => {
      finish = resolve;
    });
  });
});

function setup(markdown = "A. Old.") {
  return renderHook(() => useHumanizeStream({ sectionId: "a:0", currentMarkdown: markdown }));
}

describe("useHumanizeStream", () => {
  it("POSTs to the stream url and accumulates pass events", async () => {
    const { result } = setup();
    act(() => result.current.run());
    await waitFor(() => expect(consume).toHaveBeenCalled());
    const [url, opts] = consume.mock.calls[0];
    expect(url).toBe("http://api/api/v1/content/humanize-preview/stream");
    expect(opts.method).toBe("POST");
    expect(opts.body).toEqual({ section_id: "a:0", current_markdown: "A. Old." });
    expect(opts.token).toBe("T");
    act(() => emit("pass", PASS0));
    act(() => emit("pass", PASS1));
    expect(result.current.status).toBe("streaming");
    expect(result.current.passes).toHaveLength(2);
  });

  it("done → all changes accepted; toggle/rejectAll/acceptAll drive resolvedMarkdown", async () => {
    const { result } = setup();
    act(() => result.current.run());
    await waitFor(() => expect(consume).toHaveBeenCalled());
    act(() => emit("done", DONE));
    act(() => finish());
    await waitFor(() => expect(result.current.status).toBe("done"));
    expect(result.current.resolvedMarkdown).toBe("A. New.");
    act(() => result.current.toggle("s1"));
    expect(result.current.resolvedMarkdown).toBe("A. Old.");
    act(() => result.current.acceptAll());
    expect(result.current.resolvedMarkdown).toBe("A. New.");
    act(() => result.current.rejectAll());
    expect(result.current.rejected.has("s1")).toBe(true);
  });

  it("error event sets status=error with the message", async () => {
    const { result } = setup("A.");
    act(() => result.current.run());
    await waitFor(() => expect(consume).toHaveBeenCalled());
    act(() => emit("error", { message: "llm down" }));
    act(() => finish());
    await waitFor(() => expect(result.current.status).toBe("error"));
    expect(result.current.error).toBe("llm down");
  });

  it("stream ending without done is an error", async () => {
    const { result } = setup("A.");
    act(() => result.current.run());
    await waitFor(() => expect(consume).toHaveBeenCalled());
    act(() => finish());
    await waitFor(() => expect(result.current.status).toBe("error"));
  });

  it("cancel aborts the stream and returns to idle", async () => {
    const { result } = setup("A.");
    act(() => result.current.run());
    await waitFor(() => expect(consume).toHaveBeenCalled());
    const opts = consume.mock.calls[0][1] as { signal: AbortSignal };
    act(() => result.current.cancel());
    expect(opts.signal.aborted).toBe(true);
    expect(result.current.status).toBe("idle");
  });
});
