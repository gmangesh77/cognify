"use client";

import { useState } from "react";
import { Copy, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ShowToast } from "@/components/ui/toaster";
import {
  NOT_CONNECTED_MESSAGE,
  useLinkedInRepurpose,
} from "@/hooks/use-linkedin-repurpose";

export interface LinkedInRepurposeModalProps {
  open: boolean;
  articleId: string;
  onClose: () => void;
  onToast: ShowToast;
}

const MAX_CHARS = 3000;

const RATING_STYLES: Record<string, { label: string; className: string }> = {
  HUMAN: { label: "Human", className: "bg-success-light text-success" },
  MOSTLY_HUMAN: {
    label: "Mostly human",
    className: "bg-warning-light text-warning",
  },
  LIKELY_AI: { label: "Likely AI", className: "bg-error-light text-error" },
  PURE_SLOP: { label: "Likely AI", className: "bg-error-light text-error" },
};

export function LinkedInRepurposeModal({
  open,
  articleId,
  onClose,
  onToast,
}: LinkedInRepurposeModalProps) {
  const [instruction, setInstruction] = useState("");
  const { draft, text, setText, generate, publish, busy, error, publishedUrl } =
    useLinkedInRepurpose({ articleId, showToast: onToast });

  if (!open) return null;

  const overLimit = text.length > MAX_CHARS;
  const disconnected = error === NOT_CONNECTED_MESSAGE;
  const published = publishedUrl !== null;
  const rating = draft ? RATING_STYLES[draft.slop_rating] : null;

  async function handleCopy() {
    await navigator.clipboard.writeText(text);
    onToast("Copied");
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-label="Repurpose for LinkedIn"
        className="w-full max-w-xl rounded-lg border border-neutral-200 bg-white p-6 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between gap-3">
          <h2 className="font-heading text-lg font-semibold text-neutral-900">
            Repurpose for LinkedIn
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="text-neutral-400 hover:text-neutral-600"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <label className="mt-4 flex flex-col gap-1">
          <span className="text-xs font-medium uppercase tracking-wide text-neutral-500">
            Instruction (optional)
          </span>
          <input
            type="text"
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder="e.g. lead with the security angle"
            className="rounded-md border border-neutral-200 px-3 py-2 text-sm text-neutral-900 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
        </label>

        {error ? (
          <p role="alert" className="mt-3 text-xs text-error">
            {error}
          </p>
        ) : null}

        {!draft ? (
          <div className="mt-4 flex justify-end">
            <button
              type="button"
              onClick={() => generate(instruction.trim() || undefined)}
              disabled={busy}
              className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-60"
            >
              {busy ? "Generating…" : "Generate"}
            </button>
          </div>
        ) : (
          <>
            <div className="mt-4 flex items-center justify-between gap-2">
              {rating ? (
                <span
                  className={cn(
                    "rounded-full px-2.5 py-0.5 text-xs font-medium",
                    rating.className,
                  )}
                >
                  {rating.label}
                </span>
              ) : (
                <span />
              )}
              <span
                className={cn(
                  "text-xs font-medium",
                  overLimit ? "text-error" : "text-neutral-500",
                )}
              >
                {text.length} / {MAX_CHARS}
              </span>
            </div>

            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={12}
              data-testid="linkedin-post-text"
              className="mt-2 w-full rounded-md border border-neutral-200 px-3 py-2 text-sm text-neutral-900 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
            />

            {draft.truncated ? (
              <p className="mt-1 text-xs text-warning">Truncated to fit.</p>
            ) : null}

            {publishedUrl ? (
              <p className="mt-2 text-xs text-success">
                Posted:{" "}
                <a
                  href={publishedUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline"
                >
                  {publishedUrl}
                </a>
              </p>
            ) : null}

            <footer className="mt-4 flex items-center justify-between gap-2 border-t border-neutral-100 pt-3">
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => generate(instruction.trim() || undefined)}
                  disabled={busy}
                  className="inline-flex items-center justify-center rounded-md bg-neutral-100 px-3 py-2 text-xs font-medium text-neutral-700 hover:bg-neutral-200 disabled:opacity-60"
                >
                  {busy ? "Regenerating…" : "Regenerate"}
                </button>
                <button
                  type="button"
                  onClick={() => void handleCopy()}
                  className="inline-flex items-center gap-1 rounded-md bg-neutral-100 px-3 py-2 text-xs font-medium text-neutral-700 hover:bg-neutral-200"
                >
                  <Copy className="h-3.5 w-3.5" /> Copy text
                </button>
              </div>
              <button
                type="button"
                onClick={() => void publish()}
                disabled={
                  busy || overLimit || disconnected || published || text.trim() === ""
                }
                title={disconnected ? "LinkedIn is not connected" : undefined}
                className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-xs font-medium text-white hover:bg-primary/90 disabled:opacity-60"
              >
                {published ? "Posted" : busy ? "Publishing…" : "Publish to LinkedIn"}
              </button>
            </footer>
          </>
        )}
      </div>
    </div>
  );
}
