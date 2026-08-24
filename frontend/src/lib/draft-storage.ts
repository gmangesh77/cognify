/** localStorage persistence for unsaved section drafts (AUTHOR-006).
 *
 * Key format `cognify:draft:{sectionId}` where sectionId is already
 * `${articleId}:${sectionIndex}` (makeSectionId), matching the plan's
 * `cognify:draft:{articleId}:{sectionIndex}`. Every access is
 * SSR-guarded and try/caught (quota, privacy mode) to a silent no-op.
 */

const PREFIX = "cognify:draft:";

export function loadDraft(sectionId: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(`${PREFIX}${sectionId}`);
  } catch {
    return null;
  }
}

export function saveDraft(sectionId: string, markdown: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(`${PREFIX}${sectionId}`, markdown);
  } catch {
    // ignore — autosave is best-effort
  }
}

export function clearDraft(sectionId: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(`${PREFIX}${sectionId}`);
  } catch {
    // ignore
  }
}
