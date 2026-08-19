import { describe, it, expect, vi, afterEach } from "vitest";
import { consumeSse } from "./consume-sse";

function streamOf(chunks: string[]) {
  const enc = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    start(c) {
      chunks.forEach((ch) => c.enqueue(enc.encode(ch)));
      c.close();
    },
  });
}

afterEach(() => vi.restoreAllMocks());

describe("consumeSse", () => {
  it("parses events split across chunks and ignores comments", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          streamOf([
            "event: snap",
            "shot\ndata: {\"a\":1}\n\n: keepalive\n\nevent: done\ndata: {\"b\":2}\n\n",
          ]),
          { status: 200 },
        ),
      ),
    );
    const seen: Array<[string, unknown]> = [];
    await consumeSse("/x", { onEvent: (t, d) => seen.push([t, d]) });
    expect(seen).toEqual([
      ["snapshot", { a: 1 }],
      ["done", { b: 2 }],
    ]);
  });

  it("sends the bearer token and rejects on non-2xx", async () => {
    const f = vi.fn<typeof fetch>(async () => new Response("nope", { status: 403 }));
    vi.stubGlobal("fetch", f);
    await expect(
      consumeSse("/x", { token: "T", onEvent: () => {} }),
    ).rejects.toThrow(/403/);
    expect(f.mock.calls[0][1]?.headers).toMatchObject({
      Authorization: "Bearer T",
    });
  });

  it("stops when aborted", async () => {
    const ctrl = new AbortController();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(new ReadableStream({ start() {} }), { status: 200 })),
    );
    const p = consumeSse("/x", { signal: ctrl.signal, onEvent: () => {} });
    ctrl.abort();
    await expect(p).resolves.toBeUndefined();
  });

  it("resolves when fetch itself rejects due to an in-flight abort", async () => {
    const ctrl = new AbortController();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new DOMException("Aborted", "AbortError");
      }),
    );
    const p = consumeSse("/x", { signal: ctrl.signal, onEvent: () => {} });
    ctrl.abort();
    await expect(p).resolves.toBeUndefined();
  });
});
