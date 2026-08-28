"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type {
  ImageSpec,
  RenderResponse,
  SpecCardState,
} from "@/types/visuals";
import { SpecFooter } from "./SpecCardFooter";
import { SpecMedia } from "./SpecCardMedia";

/**
 * Per-spec lifecycle card (Pencil Screen 2 `pb0Hz`).
 *
 * Anatomy is identical across the six states; only the visual treatment
 * changes per state. The parent owns the data and dispatches lifecycle
 * transitions via the supplied callbacks.
 *
 * States (left → right in the design):
 *   - idle        Empty hero slot + "Plan visual" CTA.
 *   - planning    Spinner + checklist (reading section, picking style…).
 *   - generating  Spinner + ETA, locked while provider call is in-flight.
 *   - done        Rendered image + role/style/aspect tags + Regenerate.
 *   - error       Red border + retry-with-cheaper CTA + skip.
 *   - refining    Image overlaid with refine-in-flight state + input.
 *
 * Media and footer treatments live in `SpecCardMedia.tsx` /
 * `SpecCardFooter.tsx` (INFRA-008 split).
 */

export interface SpecCardProps {
  spec: ImageSpec;
  state: SpecCardState;
  /** Latest render result, when available. */
  render?: RenderResponse | null;
  /** ETA string for `generating` state ("seconds 3 of 6"). */
  generationEta?: string;
  errorMessage?: string;
  /** When the spec is locked (planning/generating), all CTAs are disabled. */
  onPlan?: () => void;
  onRegenerate?: () => void;
  onEdit?: () => void;
  onRetryCheaper?: () => void;
  onSkip?: () => void;
  onRefine?: (note: string) => void;
  className?: string;
}

export function SpecCard({
  spec,
  state,
  render = null,
  generationEta,
  errorMessage,
  onPlan,
  onRegenerate,
  onEdit,
  onRetryCheaper,
  onSkip,
  onRefine,
  className,
}: SpecCardProps) {
  const [refineNote, setRefineNote] = useState("");

  const borderClass =
    state === "error"
      ? "border-error/40"
      : state === "done" || state === "refining"
      ? "border-neutral-200"
      : "border-neutral-200";

  return (
    <article
      data-state={state}
      className={cn(
        "relative flex w-full flex-col gap-3 rounded-lg border bg-white p-4 shadow-sm",
        borderClass,
        className,
      )}
      aria-busy={state === "planning" || state === "generating"}
    >
      <SpecHeader spec={spec} state={state} />
      <SpecMedia
        spec={spec}
        state={state}
        render={render}
        generationEta={generationEta}
        errorMessage={errorMessage}
      />
      <SpecFooter
        spec={spec}
        state={state}
        refineNote={refineNote}
        onRefineNoteChange={setRefineNote}
        onPlan={onPlan}
        onRegenerate={onRegenerate}
        onEdit={onEdit}
        onRetryCheaper={onRetryCheaper}
        onSkip={onSkip}
        onRefine={(note) => {
          onRefine?.(note);
          setRefineNote("");
        }}
      />
    </article>
  );
}

function SpecHeader({ spec, state }: { spec: ImageSpec; state: SpecCardState }) {
  return (
    <header className="flex items-center justify-between text-xs">
      <span className="flex items-center gap-2">
        <StatePill state={state} />
        <span className="font-medium text-neutral-700">
          {spec.role_style.replace("_", " ")}
        </span>
        {spec.visual_style ? (
          <span className="text-neutral-500">
            {humanizeStyleKey(spec.visual_style)}
          </span>
        ) : null}
        <span className="text-neutral-400">{spec.aspect_ratio}</span>
      </span>
      {spec.placement.anchor === "cover" ? (
        <span className="rounded-sm bg-primary-light px-2 py-0.5 text-xs font-medium text-primary">
          Cover
        </span>
      ) : null}
    </header>
  );
}

function StatePill({ state }: { state: SpecCardState }) {
  const styles: Record<SpecCardState, string> = {
    idle: "bg-neutral-100 text-neutral-600",
    planning: "bg-warning-light text-warning",
    generating: "bg-warning-light text-warning",
    done: "bg-success-light text-success",
    error: "bg-error-light text-error",
    refining: "bg-info-light text-info",
  };
  const label: Record<SpecCardState, string> = {
    idle: "Idle",
    planning: "Planning",
    generating: "Generating",
    done: "New",
    error: "Error",
    refining: "Refining",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-sm px-2 py-0.5 text-xs font-medium",
        styles[state],
      )}
    >
      {label[state]}
    </span>
  );
}

function humanizeStyleKey(key: string): string {
  return key
    .split("_")
    .map((p) => p[0]!.toUpperCase() + p.slice(1))
    .join(" ");
}
