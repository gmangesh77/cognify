"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { fetchImageFromUrl, uploadBrandAsset } from "@/lib/api/visuals";
import type {
  FetchUrlResponse,
  UploadResponse,
} from "@/types/visuals";

/**
 * Image Import Modal (Pencil Screen 7 `P4R0EO`).
 *
 * Two tabs share one modal shell:
 *   1. **Upload from file** — drag-drop or click-to-browse, MIME sniff
 *      and ≤10MB cap enforced server-side.
 *   2. **Fetch from URL** — SSRF-guarded fetch with explicit visible
 *      checks (scheme, host, MIME, size) before the user commits.
 *
 * The modal is presentation + glue. Server-side validation lives in the
 * Phase 4 endpoints (`/visuals/upload`, `/visuals/fetch-from-url`); the
 * UI surfaces the error from the API response without re-implementing
 * the rules.
 */

export interface ImageImportModalProps {
  open: boolean;
  onClose: () => void;
  onImported: (result: UploadResponse | FetchUrlResponse) => void;
  className?: string;
}

type Tab = "upload" | "url";

const ACCEPTED_MIME = ["image/png", "image/jpeg", "image/webp", "image/svg+xml"];

export function ImageImportModal({
  open,
  onClose,
  onImported,
  className,
}: ImageImportModalProps) {
  const [tab, setTab] = useState<Tab>("upload");

  if (!open) return null;

  return (
    <div
      data-testid="image-import-modal"
      role="dialog"
      aria-modal="true"
      aria-label="Import image"
      className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-900/40 p-6"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className={cn(
          "flex w-full max-w-3xl flex-col gap-4 rounded-lg border border-neutral-200 bg-white p-6 shadow-lg",
          className,
        )}
      >
        <header className="flex items-start justify-between">
          <div>
            <h2 className="text-xl font-heading font-semibold text-neutral-900">
              Import image
            </h2>
            <p className="text-xs text-neutral-500">
              Upload a brand asset or fetch from a URL. SSRF-guarded and
              MIME-sniffed before any bytes leave the server.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close import"
            className="rounded-md p-1 text-neutral-500 hover:bg-neutral-100"
          >
            <span aria-hidden="true">×</span>
          </button>
        </header>

        <TabBar tab={tab} onChange={setTab} />

        {tab === "upload" ? (
          <UploadTab onImported={onImported} />
        ) : (
          <FetchFromUrlTab onImported={onImported} />
        )}
      </div>
    </div>
  );
}

function TabBar({
  tab,
  onChange,
}: {
  tab: Tab;
  onChange: (t: Tab) => void;
}) {
  const tabs: Array<{ key: Tab; label: string }> = [
    { key: "upload", label: "Upload from file" },
    { key: "url", label: "Fetch from URL" },
  ];
  return (
    <div role="tablist" className="flex items-center gap-1 border-b border-neutral-100">
      {tabs.map((t) => {
        const isActive = tab === t.key;
        return (
          <button
            key={t.key}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(t.key)}
            className={cn(
              "border-b-2 px-3 py-2 text-sm font-medium transition-colors",
              isActive
                ? "border-primary text-primary"
                : "border-transparent text-neutral-500 hover:text-neutral-700",
            )}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}

function UploadTab({
  onImported,
}: {
  onImported: (result: UploadResponse) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const result = await uploadBrandAsset(file);
      onImported(result);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Upload failed";
      setError(msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div role="tabpanel" className="flex flex-col gap-3">
      <label
        htmlFor="visual-import-file"
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed bg-neutral-50 p-12 text-sm text-neutral-500 transition-colors hover:border-primary hover:bg-primary-light/20",
          file ? "border-success bg-success-light/20 text-success" : "border-neutral-300",
        )}
      >
        <span className="text-base font-medium text-neutral-700">
          Drag &amp; drop your image here
        </span>
        <span className="text-xs">
          or click to browse · PNG, JPG, WEBP, SVG · ≤ 10MB
        </span>
        <input
          id="visual-import-file"
          type="file"
          accept={ACCEPTED_MIME.join(",")}
          className="sr-only"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        {file ? (
          <span className="mt-2 text-xs text-success">
            {file.name} · {(file.size / 1024).toFixed(0)} KB
          </span>
        ) : null}
      </label>
      {error ? (
        <p role="alert" className="text-xs text-error">
          {error}
        </p>
      ) : null}
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={() => setFile(null)}
          disabled={!file || busy}
          className="inline-flex items-center justify-center rounded-md bg-neutral-100 px-3 py-2 text-sm font-medium text-neutral-700 hover:bg-neutral-200 disabled:opacity-60"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!file || busy}
          className="inline-flex items-center justify-center rounded-md bg-primary px-3 py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-60"
        >
          {busy ? "Importing…" : "Import"}
        </button>
      </div>
    </div>
  );
}

function FetchFromUrlTab({
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
