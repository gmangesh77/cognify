"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { refineSectionHtml } from "@/lib/api/visuals";

/**
 * Side-by-side HTML refine panel (Pencil Screen 6 `g6P48`).
 *
 * Lets the editor iterate on a section's rendered HTML/CSS via natural-
 * language instructions to Claude WITHOUT re-running the full content
 * pipeline. The diff stays visible until "Apply changes" is clicked —
 * the parent decides what to do with the returned fragment.
 *
 * The current Pencil design shows: left column = current HTML,
 * right column = proposed HTML (after AI), bottom = "Apply with AI"
 * textarea + chip-rail of common adjustments + footer actions.
 */

export interface SectionHtmlRefinePanelProps {
  sectionId: string;
  initialHtml: string;
  onApply: (newHtml: string) => void;
  onCancel?: () => void;
  className?: string;
}

const QUICK_PROMPTS = [
  "more concrete",
  "tighter ETA",
  "trust strip",
  "add quote pull",
];

export function SectionHtmlRefinePanel({
  sectionId,
  initialHtml,
  onApply,
  onCancel,
  className,
}: SectionHtmlRefinePanelProps) {
  const [instruction, setInstruction] = useState("");
  const [proposedHtml, setProposedHtml] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleRegenerate() {
    if (!instruction.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const result = await refineSectionHtml({
        section_id: sectionId,
        instruction: instruction.trim(),
        current_html: initialHtml,
      });
      setProposedHtml(result.html_fragment);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Refine failed";
      setError(msg);
    } finally {
      setBusy(false);
    }
  }

  function handleApply() {
    if (proposedHtml) onApply(proposedHtml);
  }

  return (
    <section
      aria-label={`Section HTML refine for ${sectionId}`}
      className={cn(
        "flex flex-col gap-4 rounded-lg border border-neutral-200 bg-white p-4 shadow-sm",
        className,
      )}
    >
      <header className="flex items-center justify-between">
        <h3 className="text-base font-heading font-semibold text-neutral-900">
          Apply with AI · side-by-side diff
        </h3>
        <span className="text-xs text-neutral-500">
          Iterates on a section&apos;s HTML/CSS without re-running the pipeline.
        </span>
      </header>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <DiffColumn label="Current" html={initialHtml} variant="current" />
        <DiffColumn
          label={proposedHtml ? "Proposed" : "(no changes yet)"}
          html={proposedHtml ?? initialHtml}
          variant={proposedHtml ? "proposed" : "current"}
        />
      </div>

      <div className="flex flex-col gap-2">
        <label
          htmlFor={`refine-instruction-${sectionId}`}
          className="text-xs font-medium text-neutral-700"
        >
          Apply with AI
        </label>
        <textarea
          id={`refine-instruction-${sectionId}`}
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          placeholder="add a 3-column grid with numbered cards, then a small trust strip…"
          rows={2}
          className="rounded-md border border-neutral-200 px-3 py-2 text-sm text-neutral-900 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
        />
        <div className="flex flex-wrap gap-2">
          {QUICK_PROMPTS.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() =>
                setInstruction((cur) => (cur ? `${cur}, ${q}` : q))
              }
              className="rounded-full bg-neutral-100 px-3 py-1 text-xs font-medium text-neutral-700 hover:bg-neutral-200"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {error ? (
        <p role="alert" className="text-xs text-error">
          {error}
        </p>
      ) : null}

      <footer className="flex items-center justify-end gap-2 border-t border-neutral-100 pt-3">
        {onCancel ? (
          <button
            type="button"
            onClick={onCancel}
            className="inline-flex items-center justify-center rounded-md bg-neutral-100 px-3 py-2 text-sm font-medium text-neutral-700 hover:bg-neutral-200"
          >
            Reset to original
          </button>
        ) : null}
        <button
          type="button"
          onClick={handleRegenerate}
          disabled={busy || !instruction.trim()}
          className="inline-flex items-center justify-center rounded-md bg-neutral-100 px-3 py-2 text-sm font-medium text-neutral-700 hover:bg-neutral-200 disabled:opacity-60"
        >
          {busy ? "Generating…" : "Regenerate"}
        </button>
        <button
          type="button"
          onClick={handleApply}
          disabled={!proposedHtml}
          className="inline-flex items-center justify-center rounded-md bg-primary px-3 py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-60"
        >
          Apply changes
        </button>
      </footer>
    </section>
  );
}

function DiffColumn({
  label,
  html,
  variant,
}: {
  label: string;
  html: string;
  variant: "current" | "proposed";
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-2 rounded-md border bg-neutral-50 p-3",
        variant === "proposed" ? "border-success/40" : "border-neutral-200",
      )}
    >
      <span
        className={cn(
          "text-xs font-medium uppercase tracking-wide",
          variant === "proposed" ? "text-success" : "text-neutral-500",
        )}
      >
        {label}
      </span>
      <div
        className="prose prose-sm max-w-none text-sm text-neutral-800"
        // eslint-disable-next-line react/no-danger
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
}
