"use client";

import { cn } from "@/lib/utils";
import type { ProviderBreakdown } from "@/hooks/use-visual-studio";
import type { RenderQuality, VisualStylesResponse } from "@/types/visuals";
import {
  QUALITY_LABELS,
  QUALITY_PRICE_USD,
  QUALITY_TO_PROVIDER,
} from "@/types/visuals";
import { StyleChipRail } from "./StyleChipRail";
import { UsageBadge } from "./UsageBadge";

/**
 * Presentational sections of the Visual Studio panel (INFRA-008 split from
 * `VisualStudio.tsx`). All state lives in `useVisualStudio`.
 */

export function PanelHeader({
  specCount,
  renderedCount,
  totalCost,
  breakdown,
  onClose,
}: {
  specCount: number;
  renderedCount: number;
  totalCost: number;
  breakdown: ProviderBreakdown[];
  onClose?: () => void;
}) {
  return (
    <header className="flex items-start justify-between">
      <div className="flex flex-col gap-1">
        <h2 className="text-xl font-heading font-semibold text-neutral-900">
          Visual Studio
        </h2>
        <p className="text-xs text-neutral-500">
          {specCount} specs · {renderedCount} rendered
        </p>
        <p className="mt-1 text-xs text-neutral-500">
          Plan, generate, and refine. Every visual stays linked to its section.
        </p>
      </div>
      <div className="flex items-center gap-2">
        <UsageBadge totalUsd={totalCost} breakdown={breakdown} />
        {onClose ? (
          <button
            type="button"
            onClick={onClose}
            aria-label="Close Visual Studio"
            className="rounded-md p-1 text-neutral-500 hover:bg-neutral-100"
          >
            <span aria-hidden="true">×</span>
          </button>
        ) : null}
      </div>
    </header>
  );
}

export function PageArtDirectionField({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      <label
        htmlFor="page-art-direction"
        className="text-xs font-medium uppercase tracking-wide text-neutral-500"
      >
        Page art direction
      </label>
      <textarea
        id="page-art-direction"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="e.g. soft natural light, slate palette, no people, editorial composition"
        rows={3}
        className="rounded-md border border-neutral-200 px-3 py-2 text-sm text-neutral-900 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
      />
    </div>
  );
}

export function DefaultStyleSection({
  styles,
  selected,
  onSelect,
}: {
  styles: VisualStylesResponse["styles"];
  selected: string | null;
  onSelect: (key: string | null) => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      <label className="text-xs font-medium uppercase tracking-wide text-neutral-500">
        Default visual style
      </label>
      {styles.length === 0 ? (
        <p className="text-xs text-neutral-400">Loading catalogue…</p>
      ) : (
        <StyleChipRail
          styles={styles}
          selected={selected}
          onSelect={onSelect}
        />
      )}
    </div>
  );
}

export function RenderQualitySection({
  quality,
  onChange,
}: {
  quality: RenderQuality;
  onChange: (q: RenderQuality) => void;
}) {
  const tiers: RenderQuality[] = ["standard", "fast", "mid", "premium"];
  return (
    <div className="flex flex-col gap-2">
      <label className="text-xs font-medium uppercase tracking-wide text-neutral-500">
        Render quality
      </label>
      <div className="grid grid-cols-2 gap-2">
        {tiers.map((tier) => {
          const isSelected = tier === quality;
          return (
            <button
              key={tier}
              type="button"
              onClick={() => onChange(tier)}
              aria-pressed={isSelected}
              className={cn(
                "flex flex-col items-start rounded-md border px-3 py-2 text-left transition-colors",
                isSelected
                  ? "border-primary bg-primary-light text-primary"
                  : "border-neutral-200 bg-white text-neutral-700 hover:bg-neutral-50",
              )}
            >
              <span className="text-xs font-medium">
                {QUALITY_LABELS[tier]}
              </span>
              <span className="text-xs text-neutral-500">
                {QUALITY_TO_PROVIDER[tier]}
              </span>
              <span className="mt-1 text-xs font-mono text-neutral-700">
                ${QUALITY_PRICE_USD[tier].toFixed(3)} / img
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
