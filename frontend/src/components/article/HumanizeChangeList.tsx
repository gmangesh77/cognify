"use client";

import { cn } from "@/lib/utils";
import type { HumanizeSegment } from "@/types/content";
import { WordDiffView } from "./WordDiffView";

export interface HumanizeChangeListProps {
  segments: HumanizeSegment[];
  rejected: ReadonlySet<string>;
  onToggle: (id: string) => void;
  onAcceptAll: () => void;
  onRejectAll: () => void;
}

const PILL =
  "rounded-md bg-neutral-100 px-2 py-1 text-[11px] font-medium text-neutral-700 hover:bg-neutral-200";

/** Per-sentence accept/reject list (AUTHOR-009). Changes start accepted. */
export function HumanizeChangeList({
  segments,
  rejected,
  onToggle,
  onAcceptAll,
  onRejectAll,
}: HumanizeChangeListProps) {
  const changes = segments.filter((s) => s.kind === "change");
  if (changes.length === 0) {
    return (
      <p className="text-xs text-neutral-500">
        No sentence changes — mechanical fixes only.
      </p>
    );
  }
  const accepted = changes.length - changes.filter((c) => rejected.has(c.id)).length;
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between text-[11px] text-neutral-500">
        <span>
          {accepted} of {changes.length} changes accepted
        </span>
        <span className="flex gap-1">
          <button
            type="button"
            onClick={onAcceptAll}
            data-testid="accept-all-changes"
            className={PILL}
          >
            Accept all
          </button>
          <button
            type="button"
            onClick={onRejectAll}
            data-testid="reject-all-changes"
            className={PILL}
          >
            Reject all
          </button>
        </span>
      </div>
      <ul className="flex flex-col gap-2">
        {changes.map((c) => {
          const isRejected = rejected.has(c.id);
          return (
            <li
              key={c.id}
              data-testid="humanize-change"
              data-rejected={isRejected ? "true" : "false"}
              className={cn(
                "flex flex-col gap-1 rounded-md border p-2",
                isRejected ? "border-neutral-200 opacity-60" : "border-success/40",
              )}
            >
              <WordDiffView ops={c.ops} ariaLabel={`Change ${c.id}`} />
              <button
                type="button"
                onClick={() => onToggle(c.id)}
                data-testid={`toggle-change-${c.id}`}
                className={cn(PILL, "self-end")}
              >
                {isRejected ? "Accept" : "Reject"}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
