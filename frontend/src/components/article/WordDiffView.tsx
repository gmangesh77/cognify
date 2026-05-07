"use client";

import { Fragment } from "react";
import { cn } from "@/lib/utils";
import type { WordDiffEntry } from "@/types/content";

/**
 * Word-level diff renderer (VISUAL-011 / Phase 8).
 *
 * Single source of truth for diff visualisation across image refine,
 * HTML refine, and prose rewrite (per plan §17.2). The backend emits
 * `WordDiffEntry[]` from `src/services/content/word_diff.py`; this
 * component just paints it.
 *
 * - `equal`     → plain neutral text
 * - `insert`    → green underline
 * - `delete`    → red strikethrough
 * - `replace`   → red strikethrough then green underline (so the
 *                 reader sees both before and after in place)
 */

export interface WordDiffViewProps {
  ops: WordDiffEntry[];
  className?: string;
  ariaLabel?: string;
}

export function WordDiffView({ ops, className, ariaLabel }: WordDiffViewProps) {
  return (
    <div
      role="group"
      aria-label={ariaLabel ?? "Word-level diff"}
      data-testid="word-diff-view"
      className={cn(
        "whitespace-pre-wrap rounded-md border border-neutral-200 bg-neutral-50 p-3 font-body text-sm text-neutral-800",
        className,
      )}
    >
      {ops.map((op, i) => (
        <Fragment key={`diff-${i}`}>{renderOp(op, i)}</Fragment>
      ))}
    </div>
  );
}

function renderOp(op: WordDiffEntry, index: number) {
  if (op.kind === "equal") {
    return (
      <span data-testid="diff-equal" key={`eq-${index}`}>
        {op.before}
      </span>
    );
  }
  if (op.kind === "insert") {
    return (
      <span
        data-testid="diff-insert"
        key={`ins-${index}`}
        className="bg-success-light/70 text-success underline decoration-success/60"
      >
        {op.after}
      </span>
    );
  }
  if (op.kind === "delete") {
    return (
      <span
        data-testid="diff-delete"
        key={`del-${index}`}
        className="bg-error-light/70 text-error line-through decoration-error/60"
      >
        {op.before}
      </span>
    );
  }
  // replace
  return (
    <span data-testid="diff-replace" key={`rep-${index}`}>
      <span className="bg-error-light/70 text-error line-through decoration-error/60">
        {op.before}
      </span>
      <span className="bg-success-light/70 text-success underline decoration-success/60">
        {op.after}
      </span>
    </span>
  );
}
