"use client";

import type { ImageSpec, SpecCardState } from "@/types/visuals";

/** Footer actions of a SpecCard, one set per lifecycle state (INFRA-008 split). */
export function SpecFooter({
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
