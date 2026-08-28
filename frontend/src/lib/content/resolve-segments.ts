import type { HumanizeSegment } from "@/types/content";

/**
 * Rebuild markdown from per-segment decisions (AUTHOR-009). Mirrors
 * `src/services/content/sentence_segments.resolve_segments`: a rejected
 * change keeps its original text, everything else takes the rewrite.
 */
export function resolveSegments(
  segments: HumanizeSegment[],
  rejected: ReadonlySet<string>,
): string {
  return segments
    .map((s) => (s.kind === "change" && rejected.has(s.id) ? s.before : s.after))
    .join("");
}

export function changeIds(segments: HumanizeSegment[]): string[] {
  return segments.filter((s) => s.kind === "change").map((s) => s.id);
}
