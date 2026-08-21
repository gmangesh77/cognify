/**
 * Shared H2 splitter for the article column and Visual Studio (L-013).
 *
 * `splitBySections` uses a lookahead, so when the markdown starts directly
 * with `## Heading` (the common case) segments[0] IS the first section, not
 * a preamble. Callers derive the 0-based H2 (outline) index as
 * `i - (hasPreamble(segments) ? 1 : 0)` — the same space as section_drafts,
 * ImagePlacement.section_index and the backend section_id.
 */
export function splitBySections(md: string): string[] {
  return md.split(/\n(?=##\s)/);
}

export function hasPreamble(segments: string[]): boolean {
  return !(segments[0]?.trimStart().startsWith("##") ?? false);
}
