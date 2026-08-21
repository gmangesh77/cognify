"use client";

import { useState } from "react";
import { History, LayoutPanelTop, RefreshCw, Wand2 } from "lucide-react";
import { AIRewritePopover } from "./AIRewritePopover";
import { HumanizationDiffPanel } from "./HumanizationDiffPanel";
import { InlineProseEditor } from "./InlineProseEditor";
import { RegeneratePopover } from "./RegeneratePopover";
import { SectionHtmlRefinePanel } from "@/components/visuals/SectionHtmlRefinePanel";

export interface ActiveSection {
  /** 0-based H2 (outline) index — same space as the backend section_id (L-013). */
  index: number;
  sectionId: string;
  markdown: string;
  paragraphIndex?: number;
  paragraphMarkdown?: string;
}

export type WorkbenchPanel = "humanize" | "rewrite" | "refine" | "regenerate";

export interface SectionEditingWorkbenchProps {
  articleId: string;
  section: ActiveSection;
  defaultPersona: string | null;
  initialPanel: WorkbenchPanel | null;
  onChange: (next: ActiveSection | null) => void;
  onToast: (message: string) => void;
  onOpenHistory: (sectionId: string) => void;
  /** Called after any persisted write so the page can `refetch()`. */
  onPersisted: () => void;
}

const PILL =
  "inline-flex items-center gap-1 rounded-md bg-neutral-100 px-3 py-1.5 text-xs font-medium text-neutral-700 hover:bg-neutral-200";
const PRIMARY = "rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-white hover:bg-primary/90";

export function SectionEditingWorkbench({
  articleId,
  section,
  defaultPersona,
  initialPanel,
  onChange,
  onToast,
  onOpenHistory,
  onPersisted,
}: SectionEditingWorkbenchProps) {
  const [panel, setPanel] = useState<WorkbenchPanel | null>(initialPanel);
  const toggle = (p: WorkbenchPanel) => setPanel((cur) => (cur === p ? null : p));
  // Stage a suggestion into the editor (not yet persisted).
  const stage = (md: string, msg: string) => {
    onChange({ ...section, markdown: md });
    setPanel(null);
    onToast(msg);
  };
  // The single reset path (shared by Cancel and every persisted write):
  // drops the staged rewrite / humanize suggestion and the editor draft.
  const close = () => {
    onChange(null);
    setPanel(null);
  };
  const persisted = (msg: string) => {
    onToast(msg);
    onPersisted();
    close();
  };

  return (
    <div className="mt-4 flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-end gap-2">
        <button
          type="button"
          onClick={() => toggle("humanize")}
          aria-pressed={panel === "humanize"}
          data-testid="open-humanize-panel"
          className={PILL}
        >
          <Wand2 className="h-3.5 w-3.5" />
          {panel === "humanize" ? "Hide humanizer" : "Humanize"}
        </button>
        <button
          type="button"
          onClick={() => toggle("rewrite")}
          aria-pressed={panel === "rewrite"}
          className={PRIMARY}
        >
          {panel === "rewrite" ? "Hide AI rewrite" : "Rewrite with AI"}
        </button>
        <button
          type="button"
          onClick={() => toggle("regenerate")}
          aria-pressed={panel === "regenerate"}
          data-testid="open-regenerate-panel"
          className={PILL}
        >
          <RefreshCw className="h-3.5 w-3.5" />
          {panel === "regenerate" ? "Hide regenerate" : "Regenerate"}
        </button>
        <button
          type="button"
          onClick={() => toggle("refine")}
          aria-pressed={panel === "refine"}
          className={PILL}
        >
          <LayoutPanelTop className="h-3.5 w-3.5" />
          {panel === "refine" ? "Hide refine" : "Refine layout"}
        </button>
        <button type="button" onClick={() => onOpenHistory(section.sectionId)} className={PILL}>
          <History className="h-3.5 w-3.5" /> History
        </button>
      </div>

      <InlineProseEditor
        key={section.sectionId}
        sectionId={section.sectionId}
        initialMarkdown={section.markdown}
        onCancel={close}
        onPersisted={(_md, vid) => persisted(`Section saved (version ${vid.slice(0, 8)})`)}
        onParagraphFocus={(paragraphIndex, paragraphMarkdown) =>
          onChange({ ...section, paragraphIndex, paragraphMarkdown })
        }
      />

      {panel === "humanize" ? (
        <HumanizationDiffPanel
          sectionId={section.sectionId}
          currentMarkdown={section.markdown}
          onAccept={(md) => stage(md, "Humanizer suggestion staged — review then save.")}
          onCancel={() => setPanel(null)}
        />
      ) : null}
      {panel === "rewrite" ? (
        <AIRewritePopover
          sectionId={section.sectionId}
          scope={section.paragraphIndex !== undefined ? "paragraph" : "section"}
          paragraphIndex={section.paragraphIndex}
          currentMarkdown={section.paragraphMarkdown ?? section.markdown}
          audiencePersona={defaultPersona}
          onAccept={(md, instr) => stage(md, `Rewrite ready — review then save (${instr.slice(0, 40)})`)}
          onCancel={() => setPanel(null)}
        />
      ) : null}
      {panel === "regenerate" ? (
        <RegeneratePopover
          articleId={articleId}
          sectionIndex={section.index}
          onAccepted={(_md, vid) => persisted(`Section regenerated (version ${vid.slice(0, 8)})`)}
          onCancel={() => setPanel(null)}
        />
      ) : null}
      {panel === "refine" ? (
        <SectionHtmlRefinePanel
          sectionId={section.sectionId}
          initialHtml={section.markdown}
          onApply={(md) => stage(md, "Refine result staged — review then save.")}
          onCancel={() => setPanel(null)}
        />
      ) : null}
    </div>
  );
}
