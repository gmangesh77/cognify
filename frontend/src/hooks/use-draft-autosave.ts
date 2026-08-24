"use client";

import { useState } from "react";
import { clearDraft, loadDraft, saveDraft } from "@/lib/draft-storage";

/** Draft state with localStorage autosave (AUTHOR-006).
 *
 * On mount, a stored draft that differs from the initial markdown is
 * restored (the caller shows an "Unsaved draft" chip). Typing keeps the
 * store in sync; matching the initial markdown clears it.
 */
export function useDraftAutosave(sectionId: string, initialMarkdown: string) {
  const [initial] = useState(() => {
    const stored = loadDraft(sectionId);
    const restore = stored !== null && stored !== initialMarkdown;
    return { draft: restore ? (stored as string) : initialMarkdown, restore };
  });
  const [draft, setDraftState] = useState(initial.draft);
  const [restored, setRestored] = useState(initial.restore);

  const setDraft = (next: string) => {
    setDraftState(next);
    if (next !== initialMarkdown) saveDraft(sectionId, next);
    else clearDraft(sectionId);
  };

  const discard = () => {
    setDraftState(initialMarkdown);
    clearDraft(sectionId);
    setRestored(false);
  };

  return {
    draft,
    setDraft,
    restored,
    discard,
    clear: () => clearDraft(sectionId),
  };
}
