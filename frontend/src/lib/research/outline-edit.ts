import type { OutlineSection } from "@/types/research";

/**
 * Pure outline-editing helpers for the outline review step (INFRA-008
 * split from `components/research/outline-review-step.tsx`).
 */

/** AUTHOR-008: new sections inherit the outline's average word budget
 * (rounded to 50) so an added section doesn't skew a short/pillar plan. */
export function averageBudget(sections: OutlineSection[]): number {
  if (sections.length === 0) return 300;
  const avg =
    sections.reduce((sum, s) => sum + s.target_word_count, 0) / sections.length;
  return Math.max(50, Math.round(avg / 50) * 50);
}

export function newSection(index: number, sections: OutlineSection[]): OutlineSection {
  return {
    index,
    title: "New section",
    description: "",
    key_points: [],
    target_word_count: averageBudget(sections),
    relevant_facets: [],
  };
}

export function reindex(sections: OutlineSection[]): OutlineSection[] {
  return sections.map((s, i) => ({ ...s, index: i }));
}

/** Swap `index` with its neighbour in `direction`; returns the same array when out of range. */
export function swapSections(
  sections: OutlineSection[],
  index: number,
  direction: -1 | 1,
): OutlineSection[] {
  const target = index + direction;
  if (target < 0 || target >= sections.length) return sections;
  const next = [...sections];
  [next[index], next[target]] = [next[target], next[index]];
  return reindex(next);
}
