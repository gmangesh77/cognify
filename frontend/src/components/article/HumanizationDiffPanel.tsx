"use client";

import { Wand2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useHumanizeStream } from "@/hooks/use-humanize-stream";
import { HumanizeChangeList } from "./HumanizeChangeList";
import { HumanizePassTiles } from "./HumanizePassTiles";

/**
 * Humanization diff panel (DASH-007, streaming since AUTHOR-009).
 *
 * Streams `POST /content/humanize-preview/stream`: one tile per pass
 * (mechanical → up to N LLM passes with a slop score after each), then a
 * per-sentence change list where every change starts accepted and the
 * editor rejects the ones they don't want. Diff rendering reuses
 * `WordDiffView` so the treatment matches the AI rewrite popover.
 *
 * The result is preview-only — accepting fires `onAccept(resolved)` and
 * the parent persists via `/content/section-update`, which runs the
 * anchor-preservation validator and appends a version row.
 */

export interface HumanizationDiffPanelProps {
  sectionId: string;
  currentMarkdown: string;
  onAccept: (newMarkdown: string) => void;
  onCancel?: () => void;
  className?: string;
}

const NEUTRAL =
  "inline-flex items-center justify-center rounded-md bg-neutral-100 px-3 py-2 text-xs font-medium text-neutral-700 hover:bg-neutral-200";
const PRIMARY =
  "inline-flex items-center justify-center rounded-md bg-primary px-3 py-2 text-xs font-medium text-white hover:bg-primary/90 disabled:opacity-60";

export function HumanizationDiffPanel({
  sectionId,
  currentMarkdown,
  onAccept,
  onCancel,
  className,
}: HumanizationDiffPanelProps) {
  const stream = useHumanizeStream({ sectionId, currentMarkdown });
  const streaming = stream.status === "streaming";

  function handleAccept() {
    if (stream.resolvedMarkdown !== null) onAccept(stream.resolvedMarkdown);
  }

  function handleClose() {
    stream.cancel();
    onCancel?.();
  }

  return (
    <section
      role="region"
      aria-label="Humanization diff panel"
      data-testid="humanization-diff-panel"
      className={cn(
        "flex flex-col gap-3 rounded-lg border border-neutral-200 bg-white p-4 shadow-sm",
        className,
      )}
    >
      <header className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Wand2 className="h-4 w-4 text-primary" />
          <h3 className="font-heading text-sm font-semibold text-neutral-900">
            Humanize prose
          </h3>
        </div>
        {stream.done ? (
          <ScoreBadgePair before={stream.done.score_before} after={stream.done.score_after} />
        ) : null}
      </header>

      {stream.error ? (
        <p role="alert" className="text-xs text-error">
          {stream.error}
        </p>
      ) : null}

      <HumanizePassTiles passes={stream.passes} streaming={streaming} />

      {stream.done ? (
        <>
          <HumanizeChangeList
            segments={stream.done.segments}
            rejected={stream.rejected}
            onToggle={stream.toggle}
            onAcceptAll={stream.acceptAll}
            onRejectAll={stream.rejectAll}
          />
          <p className="text-[11px] text-neutral-500">
            {stream.done.llm_called
              ? `LLM rewrite (${stream.done.model ?? "claude"}) · ${stream.done.passes} passes — review then accept.`
              : "Mechanical-only fixes — no LLM call needed."}
          </p>
        </>
      ) : stream.status === "idle" ? (
        <p className="text-xs text-neutral-500">
          Runs the slop scorer and, if needed, up to two Claude rewrite passes
          that preserve headings, code, and lists. Preview only — accept to
          stage the change for save.
        </p>
      ) : null}

      <footer className="flex items-center justify-end gap-2 border-t border-neutral-100 pt-3">
        {onCancel ? (
          <button type="button" onClick={handleClose} className={NEUTRAL}>
            Close
          </button>
        ) : null}
        {streaming ? (
          <button
            type="button"
            onClick={stream.cancel}
            data-testid="cancel-humanize"
            className={NEUTRAL}
          >
            Cancel
          </button>
        ) : null}
        {stream.done ? (
          <>
            <button
              type="button"
              onClick={stream.reset}
              data-testid="reject-humanize"
              className={NEUTRAL}
            >
              Reject
            </button>
            <button
              type="button"
              onClick={handleAccept}
              data-testid="accept-humanize"
              className={PRIMARY}
            >
              Accept
            </button>
          </>
        ) : (
          <button
            type="button"
            onClick={stream.run}
            disabled={streaming || !currentMarkdown.trim()}
            data-testid="run-humanize"
            className={PRIMARY}
          >
            {streaming ? `Humanizing… (pass ${stream.passes.length})` : "Run humanizer"}
          </button>
        )}
      </footer>
    </section>
  );
}

function ScoreBadgePair({ before, after }: { before: number; after: number }) {
  return (
    <div
      data-testid="humanize-score-badges"
      className="flex items-center gap-1 text-[11px] font-medium"
    >
      <span className="rounded-full bg-error-light/60 px-2 py-0.5 text-error">{before}</span>
      <span className="text-neutral-400">→</span>
      <span className="rounded-full bg-success-light/60 px-2 py-0.5 text-success">{after}</span>
    </div>
  );
}
