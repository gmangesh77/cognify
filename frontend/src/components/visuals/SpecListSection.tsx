"use client";

import { cn } from "@/lib/utils";
import type { SpecLifecycle } from "@/hooks/use-visual-studio";
import type { ImageSpec } from "@/types/visuals";
import { SpecCard } from "./SpecCard";

/** Spec list of the Visual Studio panel (INFRA-008 split from `VisualStudio.tsx`). */
export function SpecListSection({
  specs,
  lifecycles,
  onRender,
  onSkip,
  focusSectionIndex,
}: {
  specs: ImageSpec[];
  lifecycles: Record<string, SpecLifecycle>;
  onRender: (spec: ImageSpec) => void;
  onSkip: (id: string) => void;
  focusSectionIndex?: number | null;
}) {
  if (specs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 rounded-md border border-dashed border-neutral-300 bg-neutral-50 p-6 text-sm text-neutral-500">
        <span className="font-medium">No specs yet</span>
        <span className="text-xs">
          Click <strong>Plan visuals</strong> to generate ImageSpecs for this
          article.
        </span>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-xs font-medium uppercase tracking-wide text-neutral-500">
        Spec list · {specs.length} planned
      </h3>
      {specs.map((spec) => {
        const lc = lifecycles[spec.id] ?? { state: "idle", render: null };
        const specSectionIndex = spec.placement.section_index;
        const isFocused =
          focusSectionIndex != null && specSectionIndex === focusSectionIndex;
        return (
          <div
            key={spec.id}
            data-section-index={specSectionIndex}
            className={cn(
              "rounded-md transition-shadow",
              isFocused &&
                "ring-2 ring-primary ring-offset-2 ring-offset-white",
            )}
          >
            <SpecCard
              spec={spec}
              state={lc.state}
              render={lc.render}
              errorMessage={lc.error}
              onPlan={() => onRender(spec)}
              onRegenerate={() => onRender(spec)}
              onRetryCheaper={() => onRender(spec)}
              onSkip={() => onSkip(spec.id)}
            />
          </div>
        );
      })}
    </div>
  );
}
