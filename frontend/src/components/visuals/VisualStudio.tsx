"use client";

import { cn } from "@/lib/utils";
import { useVisualStudio } from "@/hooks/use-visual-studio";
import type {
  InsertedVisual,
  VisualStudioArticleContext,
} from "@/hooks/use-visual-studio";
import { SpecListSection } from "./SpecListSection";
import {
  DefaultStyleSection,
  PageArtDirectionField,
  PanelHeader,
  RenderQualitySection,
} from "./VisualStudioSections";

/**
 * Visual Studio panel (Pencil Screen 1 `lZhq7`, right column).
 *
 * Owns the user-facing state for image planning + rendering against the
 * article currently in view. The panel is presentation + orchestration —
 * state and API orchestration live in `hooks/use-visual-studio.ts`
 * (INFRA-008 split), concrete API calls in `lib/api/visuals.ts`, which
 * wraps the Phase 4 Studio API endpoints.
 *
 * The component is intentionally self-contained: parents pass the
 * article context and receive a callback when the editor wants to
 * "Insert into article" so the host page can update the canonical
 * article body.
 */

export type { InsertedVisual, VisualStudioArticleContext };

export interface VisualStudioProps {
  article: VisualStudioArticleContext;
  audiencePersona?: string | null;
  /**
   * Fires when the user clicks "Insert into article". Receives the
   * spec + the corresponding render result (image url, dimensions,
   * provider, cost). Caller is responsible for persisting them on
   * the article (e.g., POST /articles/{id}/visuals).
   */
  onInsertIntoArticle?: (visuals: InsertedVisual[]) => void;
  onClose?: () => void;
  /**
   * When set, the studio shows a breadcrumb naming the section and
   * scrolls the first matching spec card into view. Lets the article
   * page's "Edit visual" toolbar action focus the user on the right
   * section instead of dumping them into the full spec list.
   */
  focusSectionIndex?: number | null;
  className?: string;
}

export function VisualStudio({
  article,
  audiencePersona,
  onInsertIntoArticle,
  onClose,
  focusSectionIndex,
  className,
}: VisualStudioProps) {
  const studio = useVisualStudio({ article, audiencePersona, focusSectionIndex });

  function handleInsert() {
    const ready = studio.readyVisuals();
    if (ready.length > 0) onInsertIntoArticle?.(ready);
  }

  return (
    <aside
      data-testid="visual-studio-panel"
      className={cn(
        "flex h-full w-full max-w-[560px] flex-col gap-5 rounded-lg border border-neutral-200 bg-white p-6 shadow-sm",
        className,
      )}
      aria-label="Visual Studio"
    >
      <PanelHeader
        specCount={studio.specs.length}
        renderedCount={studio.renderedCount}
        totalCost={studio.totalCost}
        breakdown={studio.breakdown}
        onClose={onClose}
      />

      {studio.focusedSectionTitle ? (
        <div
          data-testid="visual-studio-focus-banner"
          className="rounded-md border border-primary/30 bg-primary-light px-3 py-2 text-xs font-medium text-primary"
        >
          Editing visual for:{" "}
          <span className="font-semibold">{studio.focusedSectionTitle}</span>
        </div>
      ) : null}

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={studio.handlePlanVisuals}
          disabled={studio.planning}
          className="inline-flex flex-1 items-center justify-center rounded-md bg-primary px-3 py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-60"
        >
          {studio.planning ? "Planning…" : "Plan visuals"}
        </button>
        <button
          type="button"
          onClick={handleInsert}
          disabled={!studio.canInsert}
          className="inline-flex flex-1 items-center justify-center rounded-md bg-neutral-100 px-3 py-2 text-sm font-medium text-neutral-700 hover:bg-neutral-200 disabled:opacity-60"
        >
          Insert into article
        </button>
      </div>

      <PageArtDirectionField
        value={studio.pageDirection}
        onChange={studio.setPageDirection}
      />

      <DefaultStyleSection
        styles={studio.styles?.styles ?? []}
        selected={studio.defaultStyleKey}
        onSelect={studio.setDefaultStyleKey}
      />

      <RenderQualitySection
        quality={studio.quality}
        onChange={studio.setQuality}
      />

      {studio.planError ? (
        <p role="alert" className="text-xs text-error">
          {studio.planError}
        </p>
      ) : null}

      <SpecListSection
        specs={studio.specs}
        lifecycles={studio.lifecycles}
        onRender={studio.handleRenderSpec}
        onSkip={studio.skipSpec}
        focusSectionIndex={focusSectionIndex ?? null}
      />
    </aside>
  );
}
