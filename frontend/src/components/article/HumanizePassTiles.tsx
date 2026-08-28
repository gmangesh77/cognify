"use client";

import { cn } from "@/lib/utils";
import type { HumanizePassEvent } from "@/types/content";

/** One tile per humanization pass, streaming in (AUTHOR-009). */
export function HumanizePassTiles({
  passes,
  streaming,
}: {
  passes: HumanizePassEvent[];
  streaming: boolean;
}) {
  if (passes.length === 0 && !streaming) return null;
  return (
    <ol data-testid="humanize-pass-tiles" className="flex flex-wrap gap-2">
      {passes.map((p) => (
        <li
          key={p.index}
          data-testid="humanize-pass-tile"
          className="flex flex-col gap-0.5 rounded-md border border-neutral-200 bg-neutral-50 px-3 py-2 text-[11px]"
        >
          <span className="font-medium text-neutral-700">
            {p.name === "mechanical" ? "Mechanical" : `LLM pass ${p.index}`}
            {p.model ? ` · ${p.model}` : ""}
          </span>
          <span className="font-mono text-neutral-600">
            {p.score_before} → {p.score_after}
          </span>
          <span className={cn(p.changed ? "text-success" : "text-neutral-400")}>
            {p.changed ? "changed" : "no change"}
          </span>
        </li>
      ))}
      {streaming ? (
        <li
          data-testid="humanize-pass-pending"
          role="status"
          className="animate-pulse rounded-md border border-dashed border-warning/40 bg-warning-light/40 px-3 py-2 text-[11px] text-warning"
        >
          Running pass {passes.length}…
        </li>
      ) : null}
    </ol>
  );
}
