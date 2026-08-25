"use client";

import { StatusBadge } from "@/components/common/status-badge";
import type { ArticleStatus } from "@/types/articles";

/** Current status pill + the forward transition (AUTHOR-007).
 *
 * Transitions are UI-guided only — the backend accepts any valid status
 * from editor+, so review flows can also move backwards via the API.
 */
const NEXT: Partial<Record<ArticleStatus, ArticleStatus>> = {
  draft: "in_review",
  in_review: "approved",
  approved: "published",
};

const NEXT_LABEL: Partial<Record<ArticleStatus, string>> = {
  draft: "Move to In Review",
  in_review: "Move to Approved",
  approved: "Move to Published",
};

interface ArticleStatusControlProps {
  status: ArticleStatus;
  onTransition: (next: ArticleStatus) => void;
  busy?: boolean;
}

export function ArticleStatusControl({
  status,
  onTransition,
  busy = false,
}: ArticleStatusControlProps) {
  const next = NEXT[status];
  return (
    <span className="flex items-center gap-2">
      <StatusBadge status={status} />
      {next ? (
        <button
          type="button"
          disabled={busy}
          onClick={() => onTransition(next)}
          className="rounded-md px-2 py-1 text-xs font-medium text-neutral-600 hover:bg-neutral-100 disabled:opacity-50"
        >
          {NEXT_LABEL[status]}
        </button>
      ) : null}
    </span>
  );
}
