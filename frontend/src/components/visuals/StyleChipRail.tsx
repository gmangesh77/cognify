"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { StyleCatalogueEntry } from "@/types/visuals";

/**
 * Horizontal scrollable rail of catalogue style chips (Pencil Screen 1
 * `lZhq7` — "Default visual style" sub-section).
 *
 * The selected chip is filled red; unselected chips are neutral pills.
 * Clicking a chip emits the catalogue key. Stays presentation-only —
 * the parent owns the selected key and the dispatch.
 *
 * The "+N more" affordance was previously a non-interactive span; it's
 * now a button that expands the rail to show every catalogue entry.
 */
export interface StyleChipRailProps {
  styles: StyleCatalogueEntry[];
  selected: string | null;
  onSelect: (key: string | null) => void;
  /** Show the +N overflow indicator after this many visible chips. */
  visibleLimit?: number;
  className?: string;
}

export function StyleChipRail({
  styles,
  selected,
  onSelect,
  visibleLimit = 6,
  className,
}: StyleChipRailProps) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? styles : styles.slice(0, visibleLimit);
  const overflow = Math.max(0, styles.length - visibleLimit);

  return (
    <div
      className={cn("flex flex-wrap items-center gap-2", className)}
      role="radiogroup"
      aria-label="Visual style selector"
    >
      {visible.map((style) => {
        const isSelected = style.key === selected;
        return (
          <button
            key={style.key}
            type="button"
            role="radio"
            aria-checked={isSelected}
            onClick={() => onSelect(isSelected ? null : style.key)}
            title={style.short_desc}
            className={cn(
              "rounded-full px-3 py-1 text-xs font-medium transition-colors",
              isSelected
                ? "bg-primary text-white"
                : "bg-neutral-100 text-neutral-700 hover:bg-neutral-200",
            )}
          >
            {style.label}
          </button>
        );
      })}
      {overflow > 0 ? (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          data-testid="style-chip-rail-toggle"
          className="rounded-full bg-neutral-50 px-3 py-1 text-xs font-medium text-neutral-600 hover:bg-neutral-100 hover:text-neutral-800"
        >
          {expanded ? "Show fewer" : `+${overflow} more`}
        </button>
      ) : null}
    </div>
  );
}
