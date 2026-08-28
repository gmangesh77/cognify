"use client";

import { useState } from "react";
import { fetchImageFromUrl } from "@/lib/api/visuals";
import type { FetchUrlResponse } from "@/types/visuals";

/** "Fetch from URL" tab of the Image Import Modal (INFRA-008 split). */
export function FetchFromUrlTab({
  onImported,
}: {
  onImported: (result: FetchUrlResponse) => void;
}) {
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [verified, setVerified] = useState<FetchUrlResponse | null>(null);

  async function handleFetch() {
    if (!url.trim()) return;
    setBusy(true);
    setError(null);
    setVerified(null);
    try {
      const result = await fetchImageFromUrl({ url: url.trim() });
      setVerified(result);
      onImported(result);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Fetch failed";
      setError(msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div role="tabpanel" className="flex flex-col gap-3">
      <label htmlFor="visual-import-url" className="text-xs font-medium text-neutral-700">
        Image URL
      </label>
      <input
        id="visual-import-url"
        type="url"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="https://your-cdn.example/path/to/image.png"
        className="rounded-md border border-neutral-200 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
      />
      <ul className="rounded-md border border-success/30 bg-success-light/40 p-3 text-xs text-success">
        <li>HTTPS scheme required</li>
        <li>Host resolves to a public address (no private CIDRs)</li>
        <li>MIME sniffed against PNG / JPG / WEBP magic bytes</li>
        <li>Size capped at 10MB (Content-Length verified)</li>
      </ul>
      {error ? (
        <p role="alert" className="text-xs text-error">
          {error}
        </p>
      ) : null}
      {verified ? (
        <p className="text-xs text-success">
          Imported · {verified.mime_type} · {(verified.size_bytes / 1024).toFixed(0)} KB
        </p>
      ) : null}
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={() => setUrl("")}
          disabled={busy}
          className="inline-flex items-center justify-center rounded-md bg-neutral-100 px-3 py-2 text-sm font-medium text-neutral-700 hover:bg-neutral-200 disabled:opacity-60"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={handleFetch}
          disabled={!url.trim() || busy}
          className="inline-flex items-center justify-center rounded-md bg-primary px-3 py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-60"
        >
          {busy ? "Fetching…" : "Fetch & import"}
        </button>
      </div>
    </div>
  );
}
