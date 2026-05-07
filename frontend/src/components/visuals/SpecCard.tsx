"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { pickGeneratedImageSrc } from "@/lib/visuals/imageSrc";
import type {
  ImageSpec,
  RenderResponse,
  SpecCardState,
} from "@/types/visuals";

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

function SpecMedia({
  spec,
  state,
  render,
  generationEta,
  errorMessage,
}: {
  spec: ImageSpec;
  state: SpecCardState;
  render: RenderResponse | null;
  generationEta?: string;
  errorMessage?: string;
}) {
  const aspectStyle = aspectToStyle(spec.aspect_ratio);
  const imageSrc = render ? pickGeneratedImageSrc(render) : null;

  if (state === "idle") {
    return (
      <div
        style={aspectStyle}
        className="flex items-center justify-center rounded-md border border-dashed border-neutral-300 bg-neutral-50 text-sm text-neutral-500"
      >
        Plan to generate
      </div>
    );
  }

  if (state === "planning") {
    return (
      <div
        style={aspectStyle}
        className="flex flex-col items-center justify-center gap-2 rounded-md bg-warning-light/50 p-4 text-warning"
        role="status"
      >
        <Spinner />
        <span className="text-sm font-medium">Planning…</span>
        <ul className="mt-1 space-y-0.5 text-xs">
          <li>Reading section</li>
          <li>Matching personas</li>
          <li>Picking styles</li>
        </ul>
      </div>
    );
  }

  if (state === "generating") {
    return (
      <div
        style={aspectStyle}
        className="flex flex-col items-center justify-center gap-2 rounded-md bg-warning-light/50 p-4 text-warning"
        role="status"
      >
        <Spinner />
        <span className="text-sm font-medium">Rendering pixels…</span>
        {generationEta ? (
          <span className="text-xs text-warning/80">{generationEta}</span>
        ) : null}
      </div>
    );
  }

  if (state === "error") {
    return (
      <div
        style={aspectStyle}
        className="flex flex-col items-center justify-center gap-1 rounded-md border border-error/30 bg-error-light p-4 text-error"
        role="alert"
      >
        <span className="text-sm font-semibold">Render failed</span>
        {errorMessage ? (
          <span className="text-xs text-error/80">{errorMessage}</span>
        ) : null}
      </div>
    );
  }

  // done | refining
  if (imageSrc) {
    return (
      <div
        style={aspectStyle}
        className="relative overflow-hidden rounded-md bg-neutral-100"
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={imageSrc}
          alt={spec.alt_text || "Generated visual"}
          className="absolute inset-0 h-full w-full object-cover"
          loading="lazy"
        />
        {state === "refining" ? (
          <div
            className="absolute inset-0 flex items-end bg-info/30 p-3 text-info"
            role="status"
          >
            <span className="text-sm font-medium">
              Refining the hero · v1 → v2 in flight
            </span>
          </div>
        ) : null}
      </div>
    );
  }
  return (
    <div
      style={aspectStyle}
      className="flex items-center justify-center rounded-md border border-neutral-200 bg-neutral-50 text-sm text-neutral-500"
    >
      No render yet
    </div>
  );
}

function SpecFooter({
  spec,
  state,
  refineNote,
  onRefineNoteChange,
  onPlan,
  onRegenerate,
  onEdit,
  onRetryCheaper,
  onSkip,
  onRefine,
}: {
  spec: ImageSpec;
  state: SpecCardState;
  refineNote: string;
  onRefineNoteChange: (v: string) => void;
  onPlan?: () => void;
  onRegenerate?: () => void;
  onEdit?: () => void;
  onRetryCheaper?: () => void;
  onSkip?: () => void;
  onRefine?: (note: string) => void;
}) {
  if (state === "idle") {
    return (
      <button
        type="button"
        onClick={onPlan}
        className="inline-flex items-center justify-center rounded-md bg-primary px-3 py-2 text-sm font-medium text-white hover:bg-primary/90"
      >
        Plan visual
      </button>
    );
  }
  if (state === "planning" || state === "generating") {
    return null;
  }
  if (state === "error") {
    return (
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onRetryCheaper}
          className="inline-flex items-center justify-center rounded-md bg-primary px-3 py-2 text-sm font-medium text-white hover:bg-primary/90"
        >
          Retry with Mid
        </button>
        <button
          type="button"
          onClick={onSkip}
          className="inline-flex items-center justify-center rounded-md bg-neutral-100 px-3 py-2 text-sm font-medium text-neutral-700 hover:bg-neutral-200"
        >
          Skip
        </button>
      </div>
    );
  }
  if (state === "refining") {
    return (
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (refineNote.trim()) {
            onRefine?.(refineNote.trim());
          }
        }}
        className="flex flex-col gap-2"
      >
        <input
          type="text"
          value={refineNote}
          onChange={(e) => onRefineNoteChange(e.target.value)}
          placeholder="Refine — e.g. softer light, more candid"
          aria-label={`Refine ${spec.id}`}
          className="rounded-md border border-neutral-200 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
        />
        <div className="flex items-center gap-2">
          <button
            type="submit"
            className="inline-flex items-center justify-center rounded-md bg-primary px-3 py-2 text-sm font-medium text-white hover:bg-primary/90"
          >
            Apply
          </button>
          <button
            type="button"
            onClick={() => onRefineNoteChange("")}
            className="inline-flex items-center justify-center rounded-md bg-neutral-100 px-3 py-2 text-sm font-medium text-neutral-700 hover:bg-neutral-200"
          >
            Cancel
          </button>
        </div>
      </form>
    );
  }
  // done
  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={onRegenerate}
        className="inline-flex items-center justify-center rounded-md bg-primary px-3 py-2 text-sm font-medium text-white hover:bg-primary/90"
      >
        Regenerate
      </button>
      <button
        type="button"
        onClick={onEdit}
        className="inline-flex items-center justify-center rounded-md bg-neutral-100 px-3 py-2 text-sm font-medium text-neutral-700 hover:bg-neutral-200"
      >
        Edit
      </button>
    </div>
  );
}

function Spinner() {
  return (
    <span
      role="presentation"
      aria-hidden="true"
      className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-warning/30 border-t-warning"
    />
  );
}

function aspectToStyle(aspect: ImageSpec["aspect_ratio"]): React.CSSProperties {
  const map: Record<ImageSpec["aspect_ratio"], string> = {
    "16:9": "16 / 9",
    "1:1": "1 / 1",
    "4:3": "4 / 3",
    "3:4": "3 / 4",
    "4:5": "4 / 5",
  };
  return { aspectRatio: map[aspect] };
}

function humanizeStyleKey(key: string): string {
  return key
    .split("_")
    .map((p) => p[0]!.toUpperCase() + p.slice(1))
    .join(" ");
}
