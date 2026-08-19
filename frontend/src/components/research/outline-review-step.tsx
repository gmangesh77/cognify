"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useOutlineReview } from "@/hooks/use-outline-review";
import { OutlineSectionEditor } from "./outline-section-editor";
import { OutlineRegeneratePanel } from "./outline-regenerate-panel";
import type { ArticleOutline, OutlineSection } from "@/types/research";

interface OutlineReviewStepProps {
  sessionId: string;
}

function newSection(index: number): OutlineSection {
  return {
    index,
    title: "New section",
    description: "",
    key_points: [],
    target_word_count: 300,
    relevant_facets: [],
  };
}

function reindex(sections: OutlineSection[]): OutlineSection[] {
  return sections.map((s, i) => ({ ...s, index: i }));
}

/** VISUAL-011-style gate step (AUTHOR-002): lets an editor review and edit
 * the LLM-generated outline before section drafting runs. Rendered by
 * SessionProgress while status === "awaiting_outline_review". */
export function OutlineReviewStep({ sessionId }: OutlineReviewStepProps) {
  const {
    outline,
    isLoading,
    save,
    regenerate,
    approve,
    isSaving,
    isRegenerating,
    isApproving,
    validationErrors,
  } = useOutlineReview(sessionId);

  const [syncedOutline, setSyncedOutline] = useState<ArticleOutline | null>(null);
  const [local, setLocal] = useState<ArticleOutline | null>(null);
  const [dirty, setDirty] = useState(false);

  // Adjust state during render (React's documented alternative to a
  // setState-in-effect) whenever the server hands us a new outline —
  // initial load, a successful regenerate, or a save that reflects back
  // the persisted copy.
  if (outline && outline.outline !== syncedOutline) {
    setSyncedOutline(outline.outline);
    setLocal(outline.outline);
    setDirty(false);
  }

  if (isLoading || !local) {
    return <p className="text-sm text-neutral-500">Loading outline…</p>;
  }

  function update(partial: Partial<ArticleOutline>) {
    setLocal((prev) => (prev ? { ...prev, ...partial } : prev));
    setDirty(true);
  }

  function updateSection(index: number, section: OutlineSection) {
    if (!local) return;
    update({ sections: local.sections.map((s, i) => (i === index ? section : s)) });
  }

  function moveSection(index: number, direction: -1 | 1) {
    if (!local) return;
    const target = index + direction;
    if (target < 0 || target >= local.sections.length) return;
    const sections = [...local.sections];
    [sections[index], sections[target]] = [sections[target], sections[index]];
    update({ sections: reindex(sections) });
  }

  function deleteSection(index: number) {
    if (!local) return;
    update({ sections: reindex(local.sections.filter((_, i) => i !== index)) });
  }

  function addSection() {
    if (!local) return;
    update({ sections: [...local.sections, newSection(local.sections.length)] });
  }

  async function handleApprove() {
    if (!local) return;
    try {
      if (dirty) {
        await save(local);
        setDirty(false);
      }
      await approve();
    } catch {
      // Surfaced to the user via `validationErrors` (derived from the
      // mutation's error state) — nothing further to do here.
    }
  }

  const busy = isSaving || isRegenerating || isApproving;

  return (
    <section className="space-y-4 rounded-lg border border-neutral-200 bg-white p-5">
      <div>
        <label
          htmlFor="outline-title"
          className="text-xs font-medium uppercase tracking-wide text-neutral-500"
        >
          Title
        </label>
        <input
          id="outline-title"
          value={local.title}
          onChange={(e) => update({ title: e.target.value })}
          className="mt-1 w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:border-primary focus:outline-none"
        />
      </div>
      <div>
        <label
          htmlFor="outline-subtitle"
          className="text-xs font-medium uppercase tracking-wide text-neutral-500"
        >
          Subtitle
        </label>
        <input
          id="outline-subtitle"
          value={local.subtitle ?? ""}
          onChange={(e) => update({ subtitle: e.target.value || null })}
          className="mt-1 w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:border-primary focus:outline-none"
        />
      </div>

      <div role="list" className="space-y-3">
        {local.sections.map((section, i) => (
          <OutlineSectionEditor
            key={i}
            section={section}
            index={i}
            total={local.sections.length}
            onChange={(s) => updateSection(i, s)}
            onMoveUp={() => moveSection(i, -1)}
            onMoveDown={() => moveSection(i, 1)}
            onDelete={() => deleteSection(i)}
          />
        ))}
      </div>

      <Button type="button" variant="ghost" onClick={addSection}>
        Add section
      </Button>

      {validationErrors.length > 0 && (
        <ul className="space-y-1 rounded-md bg-error-light p-3 text-sm text-error">
          {validationErrors.map((msg) => (
            <li key={msg}>{msg}</li>
          ))}
        </ul>
      )}

      <OutlineRegeneratePanel
        dirty={dirty}
        busy={busy}
        isRegenerating={isRegenerating}
        regenerate={regenerate}
      />

      <div className="flex justify-end border-t border-neutral-100 pt-4">
        <Button type="button" onClick={handleApprove} disabled={busy}>
          {isApproving ? "Approving…" : "Approve & write"}
        </Button>
      </div>
    </section>
  );
}
