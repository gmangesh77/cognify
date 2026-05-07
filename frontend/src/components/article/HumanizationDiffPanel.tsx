"use client";

import { useState } from "react";
import { Wand2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { previewHumanization } from "@/lib/api/content";
import type { HumanizePreviewResponse } from "@/types/content";
import { WordDiffView } from "./WordDiffView";

/**
 * Humanization diff panel (DASH-007).
 *
 * Runs the cognify slop scorer + humanizer on the active section's
 * markdown and shows the editor a word-level diff with accept/reject
 * controls. Reuses the same `WordDiffView` as the AI rewrite popover
 * so the visual treatment is consistent across image refine, HTML
 * refine, prose rewrite, and humanization.
 *
 * The result is preview-only — accepting fires `onAccept(rewritten)`
 * and the parent persists via `/content/section-update`, which runs
 * the anchor-preservation validator and appends a version row.
 */

export interface HumanizationDiffPanelProps {
  sectionId: string;
  currentMarkdown: string;
  onAccept: (newMarkdown: string) => void;
  onCancel?: () => void;
  className?: string;
}

interface PanelState {
  busy: boolean;
  error: string | null;
  result: HumanizePreviewResponse | null;
}

const INITIAL_STATE: PanelState = {
  busy: false,
  error: null,
  result: null,
};

export function HumanizationDiffPanel({
  sectionId,
  currentMarkdown,
  onAccept,
  onCancel,
  className,
}: HumanizationDiffPanelProps) {
  const [state, setState] = useState<PanelState>(INITIAL_STATE);

  async function runHumanizer() {
    setState((s) => ({ ...s, busy: true, error: null }));
    try {
      const res = await previewHumanization({
        section_id: sectionId,
        current_markdown: currentMarkdown,
      });
      setState({ busy: false, error: null, result: res });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Humanize failed";
      setState({ busy: false, error: msg, result: null });
    }
  }

  function handleAccept() {
    if (!state.result) return;
    onAccept(state.result.rewritten);
  }

  function handleReject() {
    setState(INITIAL_STATE);
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
        {state.result ? (
          <ScoreBadgePair
            before={state.result.score_before.score}
            after={state.result.score_after.score}
          />
        ) : null}
      </header>

      {state.error ? (
        <p role="alert" className="text-xs text-error">
          {state.error}
        </p>
      ) : null}

      {state.result ? (
        <>
          <WordDiffView
            ops={state.result.diff}
            ariaLabel="Humanization diff"
          />
          <p className="text-[11px] text-neutral-500">
            {state.result.llm_called
              ? `LLM rewrite (${state.result.model ?? "claude"}) — review then accept.`
              : "Mechanical-only fixes — no LLM call needed."}
          </p>
        </>
      ) : (
        <p className="text-xs text-neutral-500">
          Runs the slop scorer and, if needed, a Claude rewrite that
          preserves headings, code, and lists. Preview only — accept to
          stage the change for save.
        </p>
      )}

      <footer className="flex items-center justify-end gap-2 border-t border-neutral-100 pt-3">
        {onCancel ? (
          <button
            type="button"
            onClick={onCancel}
            className="inline-flex items-center justify-center rounded-md bg-neutral-100 px-3 py-2 text-xs font-medium text-neutral-700 hover:bg-neutral-200"
          >
            Close
          </button>
        ) : null}
        {state.result ? (
          <>
            <button
              type="button"
              onClick={handleReject}
              data-testid="reject-humanize"
              className="inline-flex items-center justify-center rounded-md bg-neutral-100 px-3 py-2 text-xs font-medium text-neutral-700 hover:bg-neutral-200"
            >
              Reject
            </button>
            <button
              type="button"
              onClick={handleAccept}
              data-testid="accept-humanize"
              className="inline-flex items-center justify-center rounded-md bg-primary px-3 py-2 text-xs font-medium text-white hover:bg-primary/90"
            >
              Accept
            </button>
          </>
        ) : (
          <button
            type="button"
            onClick={runHumanizer}
            disabled={state.busy || !currentMarkdown.trim()}
            data-testid="run-humanize"
            className="inline-flex items-center justify-center rounded-md bg-primary px-3 py-2 text-xs font-medium text-white hover:bg-primary/90 disabled:opacity-60"
          >
            {state.busy ? "Humanizing…" : "Run humanizer"}
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
      <span className="rounded-full bg-error-light/60 px-2 py-0.5 text-error">
        {before}
      </span>
      <span className="text-neutral-400">→</span>
      <span className="rounded-full bg-success-light/60 px-2 py-0.5 text-success">
        {after}
      </span>
    </div>
  );
}
