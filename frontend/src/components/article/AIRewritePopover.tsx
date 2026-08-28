"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { useAIRewrite } from "@/hooks/use-ai-rewrite";
import type { TonePreset, WordDiffEntry } from "@/types/content";
import { WordDiffView } from "./WordDiffView";

/**
 * AI rewrite popover (VISUAL-011 / Phase 8 — Pencil Screen 9 `Eyi7a`).
 *
 * Anchors next to a paragraph or section the editor is focused on.
 * Free-text instruction OR one of the four tone presets. The diff
 * stays in front of the editor until they accept or reject. Tone
 * preset names are server-side templates — the frontend never ships
 * the prompt text (handoff brief gotcha 5). API calls live in
 * `hooks/use-ai-rewrite.ts` (INFRA-008 split).
 */

const TONE_PRESETS: { key: TonePreset; label: string }[] = [
  { key: "shorter", label: "Shorter" },
  { key: "more_concrete", label: "More concrete" },
  { key: "more_conversational", label: "More conversational" },
  { key: "more_authoritative", label: "More authoritative" },
];

export interface AIRewritePopoverProps {
  sectionId: string;
  scope: "section" | "paragraph";
  paragraphIndex?: number;
  currentMarkdown: string;
  audiencePersona?: string | null;
  onAccept: (newMarkdown: string, instruction: string) => void;
  onCancel: () => void;
  className?: string;
}

export function AIRewritePopover({
  sectionId,
  scope,
  paragraphIndex,
  currentMarkdown,
  audiencePersona,
  onAccept,
  onCancel,
  className,
}: AIRewritePopoverProps) {
  const [instruction, setInstruction] = useState("");
  const { state, runRewrite, runPreset, reset } = useAIRewrite({
    sectionId,
    scope,
    paragraphIndex,
    currentMarkdown,
    audiencePersona,
  });

  function handleAccept() {
    if (!state.result) return;
    onAccept(state.result.markdown_fragment, state.result.instruction);
  }

  function handleReject() {
    reset();
    setInstruction("");
  }

  const diff: WordDiffEntry[] = state.result?.diff ?? [];

  return (
    <section
      role="dialog"
      aria-label="AI rewrite popover"
      data-testid="ai-rewrite-popover"
      className={cn(
        "z-30 flex w-[460px] flex-col gap-3 rounded-lg border border-neutral-200 bg-white p-4 shadow-lg",
        className,
      )}
    >
      <header className="flex items-center justify-between gap-3">
        <h3 className="font-heading text-sm font-semibold text-neutral-900">
          Rewrite with AI
        </h3>
        <button
          type="button"
          onClick={onCancel}
          className="text-xs font-medium text-neutral-500 hover:text-neutral-700"
        >
          Close
        </button>
      </header>

      <div className="flex flex-wrap gap-2">
        {TONE_PRESETS.map((p) => (
          <button
            key={p.key}
            type="button"
            disabled={state.busy || paragraphIndex === undefined}
            onClick={() => runPreset(p.key)}
            data-testid={`tone-preset-${p.key}`}
            className="rounded-full bg-neutral-100 px-3 py-1 text-xs font-medium text-neutral-700 hover:bg-neutral-200 disabled:opacity-60"
          >
            {p.label}
          </button>
        ))}
      </div>

      <label className="flex flex-col gap-1">
        <span className="text-xs font-medium text-neutral-700">
          Custom instruction
        </span>
        <textarea
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          placeholder="lead with the metric — 65% function-calling reliability — and tighten the second sentence"
          rows={3}
          className="rounded-md border border-neutral-200 px-3 py-2 text-sm text-neutral-900 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
        />
      </label>

      {state.error ? (
        <p role="alert" className="text-xs text-error">
          {state.error}
        </p>
      ) : null}

      {state.result ? (
        <WordDiffView ops={diff} ariaLabel="Rewrite diff" />
      ) : null}

      <footer className="flex items-center justify-end gap-2 border-t border-neutral-100 pt-3">
        {state.result ? (
          <>
            <button
              type="button"
              onClick={handleReject}
              data-testid="reject-rewrite"
              className="inline-flex items-center justify-center rounded-md bg-neutral-100 px-3 py-2 text-xs font-medium text-neutral-700 hover:bg-neutral-200"
            >
              Reject
            </button>
            <button
              type="button"
              onClick={handleAccept}
              data-testid="accept-rewrite"
              className="inline-flex items-center justify-center rounded-md bg-primary px-3 py-2 text-xs font-medium text-white hover:bg-primary/90"
            >
              Accept
            </button>
          </>
        ) : (
          <button
            type="button"
            onClick={() => runRewrite(instruction)}
            disabled={state.busy || !instruction.trim()}
            data-testid="run-ai-rewrite"
            className="inline-flex items-center justify-center rounded-md bg-primary px-3 py-2 text-xs font-medium text-white hover:bg-primary/90 disabled:opacity-60"
          >
            {state.busy ? "Generating…" : "Run AI"}
          </button>
        )}
      </footer>
    </section>
  );
}
