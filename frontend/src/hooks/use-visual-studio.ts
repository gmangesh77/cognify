"use client";

import { useEffect, useMemo, useState } from "react";
import { planVisuals, renderSpec } from "@/lib/api/visuals";
import { getVisualStylesCached } from "@/lib/visuals/visualStyles";
import {
  breakdownOf,
  idleLifecycles,
  readyVisualsOf,
  totalCostOf,
  type InsertedVisual,
  type SpecLifecycle,
  type VisualStudioArticleContext,
} from "@/lib/visuals/studio-lifecycle";
import type {
  ImageSpec,
  PlanRequest,
  PlanResponse,
  RenderQuality,
  VisualStylesResponse,
} from "@/types/visuals";
import { QUALITY_TO_PROVIDER } from "@/types/visuals";

export type {
  InsertedVisual,
  ProviderBreakdown,
  SpecLifecycle,
  VisualStudioArticleContext,
} from "@/lib/visuals/studio-lifecycle";

export interface UseVisualStudioArgs {
  article: VisualStudioArticleContext;
  audiencePersona?: string | null;
  focusSectionIndex?: number | null;
}

/**
 * State + orchestration for the Visual Studio panel (INFRA-008 split from
 * `components/visuals/VisualStudio.tsx`). Concrete API calls live in
 * `lib/api/visuals.ts`; the component only renders what this hook returns.
 */
export function useVisualStudio({
  article,
  audiencePersona,
  focusSectionIndex,
}: UseVisualStudioArgs) {
  const [styles, setStyles] = useState<VisualStylesResponse | null>(null);
  const [pageDirection, setPageDirection] = useState("");
  const [defaultStyleKey, setDefaultStyleKey] = useState<string | null>(null);
  // Default to "standard" (DALL·E 3) so the picker's first selection
  // matches the app-wide default_image_provider and doesn't force a
  // Google provider that may lack a configured API key.
  const [quality, setQuality] = useState<RenderQuality>("standard");
  const [specs, setSpecs] = useState<ImageSpec[]>([]);
  const [lifecycles, setLifecycles] = useState<Record<string, SpecLifecycle>>(
    {},
  );
  const [planning, setPlanning] = useState(false);
  const [planError, setPlanError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getVisualStylesCached()
      .then((r) => {
        if (!cancelled) setStyles(r);
      })
      .catch(() => {
        // Catalogue load failure is non-fatal — chips just render empty.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const totalCost = useMemo(() => totalCostOf(lifecycles), [lifecycles]);
  const breakdown = useMemo(() => breakdownOf(lifecycles), [lifecycles]);

  const focusedSectionTitle = useMemo(() => {
    if (focusSectionIndex == null) return null;
    const match = article.sections?.find(
      (s) => s.section_index === focusSectionIndex,
    );
    return match?.title ?? `Section ${focusSectionIndex + 1}`;
  }, [focusSectionIndex, article.sections]);

  // Scroll the first spec card matching the focused section into view
  // whenever the focus changes or the spec list updates.
  useEffect(() => {
    if (focusSectionIndex == null) return;
    const node = document.querySelector(
      `[data-section-index="${focusSectionIndex}"]`,
    );
    if (node && "scrollIntoView" in node) {
      (node as HTMLElement).scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    }
  }, [focusSectionIndex, specs]);

  function applyDefaultStyle(spec: ImageSpec): ImageSpec {
    if (!defaultStyleKey || spec.visual_style) return spec;
    return { ...spec, visual_style: defaultStyleKey };
  }

  async function handlePlanVisuals() {
    setPlanning(true);
    setPlanError(null);
    try {
      const body: PlanRequest = {
        topic: article.topic,
        article_summary: article.summary,
        page_art_direction: pageDirection || null,
        audience_persona: audiencePersona ?? null,
        plan_cover: true,
        max_images_per_section: 0,
      };
      const result: PlanResponse = await planVisuals(body);
      const next: ImageSpec[] = [];
      if (result.cover) next.push(applyDefaultStyle(result.cover));
      for (const s of result.section_specs) next.push(applyDefaultStyle(s));
      setSpecs(next);
      setLifecycles(idleLifecycles(next));
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Plan failed";
      setPlanError(msg);
    } finally {
      setPlanning(false);
    }
  }

  async function handleRenderSpec(spec: ImageSpec) {
    setLifecycles((prev) => ({
      ...prev,
      [spec.id]: { state: "generating", render: null },
    }));
    try {
      const result = await renderSpec({
        spec,
        page_direction: pageDirection || null,
        provider: QUALITY_TO_PROVIDER[quality],
      });
      setLifecycles((prev) => ({
        ...prev,
        [spec.id]: { state: "done", render: result },
      }));
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Render failed";
      setLifecycles((prev) => ({
        ...prev,
        [spec.id]: { state: "error", render: null, error: msg },
      }));
    }
  }

  function skipSpec(id: string) {
    setSpecs((prev) => prev.filter((s) => s.id !== id));
  }

  function readyVisuals(): InsertedVisual[] {
    return readyVisualsOf(specs, lifecycles);
  }

  const renderedCount = Object.values(lifecycles).filter(
    (lc) => lc.state === "done",
  ).length;
  const canInsert = specs.length > 0 && renderedCount > 0;

  return {
    styles,
    pageDirection,
    setPageDirection,
    defaultStyleKey,
    setDefaultStyleKey,
    quality,
    setQuality,
    specs,
    lifecycles,
    planning,
    planError,
    totalCost,
    breakdown,
    focusedSectionTitle,
    renderedCount,
    canInsert,
    handlePlanVisuals,
    handleRenderSpec,
    skipSpec,
    readyVisuals,
  };
}
