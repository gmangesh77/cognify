"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type {
  FetchUrlResponse,
  UploadResponse,
} from "@/types/visuals";
import { FetchFromUrlTab } from "./ImageFetchUrlTab";
import { UploadTab } from "./ImageUploadTab";

/**
 * Image Import Modal (Pencil Screen 7 `P4R0EO`).
 *
 * Two tabs share one modal shell:
 *   1. **Upload from file** — drag-drop or click-to-browse, MIME sniff
 *      and ≤10MB cap enforced server-side. (`ImageUploadTab.tsx`)
 *   2. **Fetch from URL** — SSRF-guarded fetch with explicit visible
 *      checks (scheme, host, MIME, size) before the user commits.
 *      (`ImageFetchUrlTab.tsx`)
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
