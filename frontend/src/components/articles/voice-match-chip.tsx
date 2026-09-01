"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

interface VoiceMatchChipProps {
  score: number;
  bySection: Record<string, number> | null;
  className?: string;
}

function bandClasses(score: number): string {
  if (score >= 80) return "bg-success-light text-success";
  if (score >= 60) return "bg-warning-light text-warning";
  return "bg-error-light text-error";
}

/**
 * Voice-match pill for the article sidebar (spec §7). Shares the
 * pill-plus-popover anatomy of `UsageBadge`: click toggles a
 * `role="dialog"` popover listing the per-section scores.
 */
export function VoiceMatchChip({ score, bySection, className }: VoiceMatchChipProps) {
  const [expanded, setExpanded] = useState(false);
  const sections = bySection
    ? Object.entries(bySection).sort(
        ([a], [b]) => Number(a) - Number(b),
      )
    : [];

  return (
    <div className={cn("relative inline-block", className)}>
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        aria-label={`Voice match: ${score}`}
        className={cn(
          "rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors",
          bandClasses(score),
        )}
      >
        Voice match {score}
      </button>
      {expanded ? (
        <div
          role="dialog"
          aria-label="Voice match by section"
          className={cn(
            "absolute left-0 z-20 mt-2 w-64 rounded-lg border border-neutral-200",
            "bg-white p-3 shadow-md",
          )}
        >
          <div className="mb-2 text-sm font-heading font-semibold text-neutral-900">
            Voice match {score}
          </div>
          {sections.length === 0 ? (
            <p className="text-xs text-neutral-500">No section scores yet.</p>
          ) : (
            <ul className="space-y-1 text-xs text-neutral-700">
              {sections.map(([index, sectionScore]) => (
                <li key={index}>
                  {`Section ${Number(index) + 1} — ${sectionScore}`}
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
