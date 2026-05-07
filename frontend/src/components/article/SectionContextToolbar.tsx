"use client";

import { ImageIcon, LayoutPanelTop, Pencil } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Floating section-level action toolbar (Pencil Screen 9 `Eyi7a`).
 *
 * Surfaces three actions over a hovered / focused section:
 *
 * - **Edit text** — opens the inline prose editor + AI rewrite popover.
 * - **Edit visual** — jumps the parent page to that section's Spec
 *   Card in Visual Studio (parent decides how to scroll / open).
 * - **Refine layout** — opens the existing `SectionHtmlRefinePanel`
 *   scoped to this section.
 *
 * The toolbar itself is presentational — keyboard focus and visibility
 * are managed by the parent (the article-detail page wraps each
 * section in a hover container that mounts the toolbar).
 */

export interface SectionContextToolbarProps {
  sectionId: string;
  sectionIndex: number;
  visible: boolean;
  onEditText: () => void;
  onEditVisual: () => void;
  onRefineLayout: () => void;
  className?: string;
}

export function SectionContextToolbar({
  sectionId,
  sectionIndex,
  visible,
  onEditText,
  onEditVisual,
  onRefineLayout,
  className,
}: SectionContextToolbarProps) {
  if (!visible) return null;
  return (
    <div
      role="toolbar"
      aria-label={`Section ${sectionIndex} actions`}
      data-testid={`section-context-toolbar-${sectionIndex}`}
      data-section-id={sectionId}
      className={cn(
        "absolute right-2 top-2 z-20 flex items-center gap-1 rounded-full border border-neutral-200 bg-white px-1 py-1 shadow-sm",
        className,
      )}
    >
      <ToolbarButton
        icon={<Pencil className="h-3.5 w-3.5" />}
        label="Edit text"
        onClick={onEditText}
        testId={`toolbar-edit-text-${sectionIndex}`}
      />
      <ToolbarButton
        icon={<ImageIcon className="h-3.5 w-3.5" />}
        label="Edit visual"
        onClick={onEditVisual}
        testId={`toolbar-edit-visual-${sectionIndex}`}
      />
      <ToolbarButton
        icon={<LayoutPanelTop className="h-3.5 w-3.5" />}
        label="Refine layout"
        onClick={onRefineLayout}
        testId={`toolbar-refine-layout-${sectionIndex}`}
      />
    </div>
  );
}

interface ToolbarButtonProps {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  testId: string;
}

function ToolbarButton({ icon, label, onClick, testId }: ToolbarButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={testId}
      className="inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium text-neutral-700 hover:bg-neutral-100"
    >
      {icon}
      <span>{label}</span>
    </button>
  );
}
