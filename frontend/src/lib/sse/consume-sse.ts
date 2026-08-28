export interface ConsumeSseOptions {
  token?: string | null;
  signal?: AbortSignal;
  /** AUTHOR-009: POST-SSE (JSON body). Default GET. */
  method?: "GET" | "POST";
  body?: unknown;
  onEvent: (type: string, data: unknown) => void;
}

function dispatchFrame(frame: string, onEvent: ConsumeSseOptions["onEvent"]) {
  let type = "message";
  const dataLines: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith(":") || line === "") continue;
    if (line.startsWith("event:")) type = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  if (dataLines.length === 0) return;
  const raw = dataLines.join("\n");
  let data: unknown = raw;
  try {
    data = JSON.parse(raw);
  } catch {
    /* plain text payload */
  }
  onEvent(type, data);
}

async function pumpFrames(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  onEvent: ConsumeSseOptions["onEvent"],
): Promise<void> {
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      dispatchFrame(buffer.slice(0, idx), onEvent);
      buffer = buffer.slice(idx + 2);
    }
  }
  if (buffer.trim()) dispatchFrame(buffer, onEvent);
}

function isAbortError(err: unknown): boolean {
  return err instanceof Error && err.name === "AbortError";
}

async function consumeBody(
  body: ReadableStream<Uint8Array>,
  opts: ConsumeSseOptions,
): Promise<void> {
  const reader = body.getReader();
  const onAbort = () => {
    void reader.cancel().catch(() => {});
  };
  if (opts.signal?.aborted) onAbort();
  else opts.signal?.addEventListener("abort", onAbort);
  try {
    await pumpFrames(reader, opts.onEvent);
  } finally {
    opts.signal?.removeEventListener("abort", onAbort);
  }
}

export async function consumeSse(url: string, opts: ConsumeSseOptions): Promise<void> {
  if (opts.signal?.aborted) return;
  const headers: Record<string, string> = { Accept: "text/event-stream" };
  if (opts.token) headers.Authorization = `Bearer ${opts.token}`;
  try {
    const init: RequestInit = { headers, signal: opts.signal, credentials: "include" };
    if (opts.method === "POST") {
      init.method = "POST";
      headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(opts.body ?? {});
    }
    const res = await fetch(url, init);
    if (!res.ok || !res.body) throw new Error(`SSE request failed: ${res.status}`);
    await consumeBody(res.body, opts);
  } catch (err) {
    if (isAbortError(err) || opts.signal?.aborted) return;
    throw err;
  }
}
