"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { uploadBrandAsset } from "@/lib/api/visuals";
import type { UploadResponse } from "@/types/visuals";

/** "Upload from file" tab of the Image Import Modal (INFRA-008 split). */

const ACCEPTED_MIME = ["image/png", "image/jpeg", "image/webp", "image/svg+xml"];

export function UploadTab({
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
