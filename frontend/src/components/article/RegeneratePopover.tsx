"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { persistSectionUpdate } from "@/lib/api/content";
import { useSectionRegenerate } from "@/hooks/use-section-regenerate";
import { WordDiffView } from "./WordDiffView";

/**
 * Regenerate-with-feedback popover (AUTHOR-004).
 *
 * Same anatomy as `AIRewritePopover` (header/Close, instruction textarea,
 * error alert, WordDiffView, Reject/Accept vs Run footer) but the
 * instruction is OPTIONAL and Accept persists immediately through
 * `/content/section-update` with `source: "regenerate"`, using the
 * `section_id` the regenerate response returned (outline space, L-013).
 */
export interface RegeneratePopoverProps {
  articleId: string;
  sectionIndex: number;
  onAccepted: (newMarkdown: string, versionId: string) => void;
  onCancel: () => void;
  className?: string;
}

const BUTTON_PRIMARY =
  "inline-flex items-center justify-center rounded-md bg-primary px-3 py-2 text-xs font-medium text-white hover:bg-primary/90 disabled:opacity-60";
const BUTTON_SECONDARY =
  "inline-flex items-center justify-center rounded-md bg-neutral-100 px-3 py-2 text-xs font-medium text-neutral-700 hover:bg-neutral-200";

export function RegeneratePopover({
  articleId,
  sectionIndex,
  onAccepted,
  onCancel,
  className,
}: RegeneratePopoverProps) {
  const [instruction, setInstruction] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const regen = useSectionRegenerate();

  async function handleRun() {
    setSaveError(null);
    await regen.run({
      article_id: articleId,
      section_index: sectionIndex,
      instruction: instruction.trim() || null,
    });
  }

  async function handleAccept() {
    if (!regen.result) return;
    setSaving(true);
    setSaveError(null);
    try {
      const saved = await persistSectionUpdate({
        section_id: regen.result.section_id,
        markdown: regen.result.markdown,
        source: "regenerate",
        instruction: regen.result.instruction ?? undefined,
      });
      onAccepted(saved.persisted_markdown, saved.version_id);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  const error = saveError ?? regen.error;

  return (
    <section
      role="dialog"
      aria-label="Regenerate section popover"
      data-testid="regenerate-popover"
      className={cn(
        "z-30 flex w-[460px] flex-col gap-3 rounded-lg border border-neutral-200 bg-white p-4 shadow-lg",
        className,
      )}
    >
      <header className="flex items-center justify-between gap-3">
        <h3 className="font-heading text-sm font-semibold text-neutral-900">Regenerate section</h3>
        <button
          type="button"
          onClick={onCancel}
          className="text-xs font-medium text-neutral-500 hover:text-neutral-700"
        >
          Close
        </button>
      </header>

      <label className="flex flex-col gap-1">
        <span className="text-xs font-medium text-neutral-700">Instruction (optional)</span>
        <textarea
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          placeholder="e.g. open with a concrete incident, keep it under 250 words"
          rows={3}
          maxLength={2000}
          data-testid="regenerate-instruction"
          className="rounded-md border border-neutral-200 px-3 py-2 text-sm text-neutral-900 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
        />
      </label>

      {error ? (
        <p role="alert" className="text-xs text-error">
          {error}
        </p>
      ) : null}
      {regen.violations.length > 0 ? (
        <ul
          data-testid="regenerate-violations"
          className="list-disc space-y-1 rounded-md border border-error/40 bg-error-light p-3 pl-6 text-xs text-error"
        >
          {regen.violations.map((v) => (
            <li key={`${v.kind}-${v.value}`}>{v.message}</li>
          ))}
        </ul>
      ) : null}

      {regen.result ? (
        <>
          <p data-testid="regenerate-meta" className="text-xs text-neutral-500">
            {regen.result.word_count} words · {regen.result.model}
          </p>
          <WordDiffView ops={regen.result.diff} ariaLabel="Regenerate diff" />
        </>
      ) : null}

      <footer className="flex items-center justify-end gap-2 border-t border-neutral-100 pt-3">
        {regen.result ? (
          <>
            <button
              type="button"
              onClick={regen.reset}
              data-testid="reject-regenerate"
              className={BUTTON_SECONDARY}
            >
              Reject
            </button>
            <button
              type="button"
              onClick={handleAccept}
              disabled={saving}
              data-testid="accept-regenerate"
              className={BUTTON_PRIMARY}
            >
              {saving ? "Saving…" : "Accept"}
            </button>
          </>
        ) : (
          <button
            type="button"
            onClick={handleRun}
            disabled={regen.busy}
            data-testid="run-regenerate"
            className={BUTTON_PRIMARY}
          >
            {regen.busy ? "Regenerating…" : "Regenerate"}
          </button>
        )}
      </footer>
    </section>
  );
}
