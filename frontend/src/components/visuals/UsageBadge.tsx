"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

/**
 * Cost badge for the Visual Studio top bar (Pencil Screen 8 `TVcmU`).
 *
 * Three states (left → right in the design):
 *   1. Compact   — pill showing "$0.043 this article"
 *   2. Expanded  — provider breakdown table when hovered/clicked
 *   3. Limit-warning — pill turns red when within 20% of the configured
 *                       per-article cost cap (drives the upstream
 *                       budget controller).
 *
 * The actual cost numbers are owned by the backend (`GET /visuals/cost`).
 * For Phase 5 we expose the props the parent screen will plumb in.
 */

export interface UsageBadgeBreakdownEntry {
  provider: string;
  count: number;
  usd: number;
}

export interface UsageBadgeProps {
  totalUsd: number;
  budgetUsd?: number | null;
  breakdown?: UsageBadgeBreakdownEntry[];
  /** When true, render only the warning pill state regardless of total. */
  forceWarning?: boolean;
  className?: string;
}

export function UsageBadge({
  totalUsd,
  budgetUsd = null,
  breakdown = [],
  forceWarning = false,
  className,
}: UsageBadgeProps) {
  const [expanded, setExpanded] = useState(false);
  const isWarning =
    forceWarning ||
    (budgetUsd !== null && budgetUsd > 0 && totalUsd >= budgetUsd * 0.8);
  const formattedTotal = `$${totalUsd.toFixed(3)}`;

  return (
    <div className={cn("relative inline-block", className)}>
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        aria-label={`Cost: ${formattedTotal} this article`}
        className={cn(
          "rounded-full px-3 py-1 text-xs font-medium transition-colors",
          isWarning
            ? "bg-error-light text-error"
            : "bg-primary text-white hover:bg-primary/90",
        )}
      >
        {formattedTotal} this article
      </button>
      {expanded ? (
        <div
          role="dialog"
          aria-label="Provider cost breakdown"
          className={cn(
            "absolute right-0 z-20 mt-2 w-64 rounded-lg border border-neutral-200",
            "bg-white p-3 shadow-md",
          )}
        >
          <div className="mb-2 text-sm font-heading font-semibold text-neutral-900">
            {formattedTotal} this article
          </div>
          {breakdown.length === 0 ? (
            <p className="text-xs text-neutral-500">No spend yet.</p>
          ) : (
            <ul className="space-y-1 text-xs text-neutral-700">
              {breakdown.map((row) => (
                <li
                  key={row.provider}
                  className="flex items-center justify-between"
                >
                  <span className="font-mono">{row.provider}</span>
                  <span className="text-neutral-500">
                    {row.count} × ${row.usd.toFixed(3)}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {budgetUsd !== null && budgetUsd > 0 ? (
            <div className="mt-2 flex items-center justify-between text-xs">
              <span className="text-neutral-500">Budget</span>
              <span className="font-medium text-neutral-700">
                ${(budgetUsd - totalUsd).toFixed(2)} remaining
              </span>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
