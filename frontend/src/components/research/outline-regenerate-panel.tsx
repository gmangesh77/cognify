"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";

interface OutlineRegeneratePanelProps {
  /** True when the local outline has unsaved edits — regenerating would
   * silently discard them, so we confirm first. */
  dirty: boolean;
  busy: boolean;
  isRegenerating: boolean;
  regenerate: (instruction?: string) => Promise<unknown>;
}

/** Instruction input + "Regenerate outline" action for OutlineReviewStep,
 * split out to keep the parent component under the project's 200-line
 * file limit. */
export function OutlineRegeneratePanel({
  dirty,
  busy,
  isRegenerating,
  regenerate,
}: OutlineRegeneratePanelProps) {
  const [instruction, setInstruction] = useState("");
  const [confirming, setConfirming] = useState(false);

  async function run() {
    try {
      await regenerate(instruction || undefined);
      setConfirming(false);
      setInstruction("");
    } catch {
      // Surfaced to the user via the parent's validationErrors.
    }
  }

  function handleClick() {
    if (dirty) {
      setConfirming(true);
      return;
    }
    void run();
  }

  return (
    <div className="space-y-2 border-t border-neutral-100 pt-4">
      <label
        htmlFor="regenerate-instruction"
        className="text-xs font-medium uppercase tracking-wide text-neutral-500"
      >
        Regenerate instruction (optional)
      </label>
      <input
        id="regenerate-instruction"
        value={instruction}
        onChange={(e) => setInstruction(e.target.value)}
        placeholder="e.g. focus more on enterprise use cases"
        className="w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:border-primary focus:outline-none"
      />
      {confirming ? (
        <div className="flex items-center gap-2 text-sm text-neutral-700">
          <span>Discard local edits and regenerate?</span>
          <Button type="button" size="sm" onClick={run} disabled={busy}>
            Discard &amp; regenerate
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => setConfirming(false)}
          >
            Keep edits
          </Button>
        </div>
      ) : (
        <Button type="button" variant="secondary" onClick={handleClick} disabled={busy}>
          {isRegenerating ? "Regenerating…" : "Regenerate outline"}
        </Button>
      )}
    </div>
  );
}
