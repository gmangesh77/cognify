import { hasPreamble, splitBySections } from "./split-sections";

export interface StudioSection {
  section_index: number;
  title: string;
  body_markdown: string;
}

/**
 * Outline-space sections for `VisualStudio`. Replaces the page's old
 * `segments.slice(1)` which assumed a prelude and dropped the first section
 * of every no-prelude article (shifting `ImagePlacement.section_index` by one).
 */
export function studioSectionsFrom(bodyMarkdown: string): StudioSection[] {
  const segments = splitBySections(bodyMarkdown);
  const offset = hasPreamble(segments) ? 1 : 0;
  return segments.slice(offset).map((segment, i) => {
    const titleMatch = segment.match(/^##\s+(.+)/);
    return {
      section_index: i,
      title: titleMatch ? titleMatch[1].trim() : `Section ${i + 1}`,
      body_markdown: segment,
    };
  });
}
