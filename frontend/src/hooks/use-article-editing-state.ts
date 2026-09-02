"use client";

import { useState } from "react";
import type {
  ActiveSection,
  WorkbenchPanel,
} from "@/components/article/SectionEditingWorkbench";
import { makeSectionId } from "@/lib/api/content";

/** Section-editing state cluster for the article detail page (AUTHOR-006
 * split — keeps `articles/[id]/page.tsx` under the 200-line budget). */
export function useArticleEditingState(articleId: string) {
  const [activeSection, setActiveSection] = useState<ActiveSection | null>(null);
  const [panel, setPanel] = useState<WorkbenchPanel | null>(null);
  const [historySectionId, setHistorySectionId] = useState<string | null>(null);
  const [focusVisualSection, setFocusVisualSection] = useState<number | null>(null);
  // AUTHOR-013 — LinkedIn repurpose modal open/closed.
  const [linkedinOpen, setLinkedinOpen] = useState(false);

  const openSection = (
    sectionIndex: number,
    markdown: string,
    nextPanel: WorkbenchPanel | null,
  ) => {
    setActiveSection({
      index: sectionIndex,
      sectionId: makeSectionId(articleId, sectionIndex),
      markdown,
    });
    setPanel(nextPanel);
  };

  return {
    activeSection,
    setActiveSection,
    panel,
    setPanel,
    historySectionId,
    setHistorySectionId,
    focusVisualSection,
    setFocusVisualSection,
    openSection,
    linkedinOpen,
    setLinkedinOpen,
  };
}
