"use client";

/** "Unsaved draft restored" pill + Discard action (AUTHOR-006 autosave). */
export function UnsavedDraftChip({ onDiscard }: { onDiscard: () => void }) {
  return (
    <div className="flex items-center gap-2">
      <span
        data-testid="unsaved-draft-chip"
        className="rounded-full bg-warning-light px-2.5 py-0.5 text-xs font-medium text-warning"
      >
        Unsaved draft restored
      </span>
      <button
        type="button"
        onClick={onDiscard}
        className="text-xs text-neutral-500 underline hover:text-neutral-700"
      >
        Discard
      </button>
    </div>
  );
}
