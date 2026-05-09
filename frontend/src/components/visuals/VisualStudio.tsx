"use client";

import { useEffect, useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import { planVisuals, renderSpec } from "@/lib/api/visuals";
import { getVisualStylesCached } from "@/lib/visuals/visualStyles";
import type {
  ImageSpec,
  PlanRequest,
  PlanResponse,
  RenderQuality,
  RenderResponse,
  SpecCardState,
  VisualStylesResponse,
} from "@/types/visuals";
import {
  QUALITY_LABELS,
  QUALITY_PRICE_USD,
  QUALITY_TO_PROVIDER,
} from "@/types/visuals";
import { SpecCard } from "./SpecCard";
import { StyleChipRail } from "./StyleChipRail";
import { UsageBadge } from "./UsageBadge";

/**
 * Visual Studio panel (Pencil Screen 1 `lZhq7`, right column).
 *
 * Owns the user-facing state for image planning + rendering against the
 * article currently in view. The panel is presentation + orchestration —
 * concrete API calls live in `frontend/src/lib/api/visuals.ts`, which
 * wraps the Phase 4 Studio API endpoints.
 *
 * The component is intentionally self-contained: parents pass the
 * article context and receive a callback when the editor wants to
 * "Insert into article" so the host page can update the canonical
 * article body.
 */

export interface VisualStudioArticleContext {
  topic: { title: string; description: string; domain: string };
  summary: string;
  /**
   * Sections we offer planning for. The MVP slice plans cover-only;
   * a future iteration will let the user pick a section to plan.
   */
  sections?: Array<{
    section_index: number;
    title: string;
    body_markdown: string;
  }>;
}

export interface VisualStudioProps {
  article: VisualStudioArticleContext;
  audiencePersona?: string | null;
  onInsertIntoArticle?: (specs: ImageSpec[]) => void;
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

interface SpecLifecycle {
  state: SpecCardState;
  render: RenderResponse | null;
  error?: string;
}

export function VisualStudio({
  article,
  audiencePersona,
  onInsertIntoArticle,
  onClose,
  focusSectionIndex,
  className,
}: VisualStudioProps) {
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

  const totalCost = useMemo(() => {
    return Object.values(lifecycles).reduce(
      (sum, lc) => sum + (lc.render?.cost_usd ?? 0),
      0,
    );
  }, [lifecycles]);

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

  const breakdown = useMemo(() => {
    const map = new Map<string, { count: number; usd: number }>();
    for (const lc of Object.values(lifecycles)) {
      if (lc.render && lc.render.provider) {
        const cur = map.get(lc.render.provider) ?? { count: 0, usd: 0 };
        cur.count += 1;
        cur.usd += lc.render.cost_usd ?? 0;
        map.set(lc.render.provider, cur);
      }
    }
    return [...map.entries()].map(([provider, v]) => ({
      provider,
      count: v.count,
      usd: v.usd,
    }));
  }, [lifecycles]);

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
      setLifecycles(
        Object.fromEntries(
          next.map((s) => [s.id, { state: "idle", render: null }]),
        ),
      );
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

  function handleInsert() {
    const ready = specs.filter(
      (s) => lifecycles[s.id]?.state === "done",
    );
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
        specCount={specs.length}
        renderedCount={
          Object.values(lifecycles).filter((lc) => lc.state === "done").length
        }
        totalCost={totalCost}
        breakdown={breakdown}
        onClose={onClose}
      />

      {focusedSectionTitle ? (
        <div
          data-testid="visual-studio-focus-banner"
          className="rounded-md border border-primary/30 bg-primary-light px-3 py-2 text-xs font-medium text-primary"
        >
          Editing visual for:{" "}
          <span className="font-semibold">{focusedSectionTitle}</span>
        </div>
      ) : null}

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={handlePlanVisuals}
          disabled={planning}
          className="inline-flex flex-1 items-center justify-center rounded-md bg-primary px-3 py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-60"
        >
          {planning ? "Planning…" : "Plan visuals"}
        </button>
        <button
          type="button"
          onClick={handleInsert}
          disabled={
            specs.length === 0 ||
            !Object.values(lifecycles).some((lc) => lc.state === "done")
          }
          className="inline-flex flex-1 items-center justify-center rounded-md bg-neutral-100 px-3 py-2 text-sm font-medium text-neutral-700 hover:bg-neutral-200 disabled:opacity-60"
        >
          Insert into article
        </button>
      </div>

      <PageArtDirectionField
        value={pageDirection}
        onChange={setPageDirection}
      />

      <DefaultStyleSection
        styles={styles?.styles ?? []}
        selected={defaultStyleKey}
        onSelect={setDefaultStyleKey}
      />

      <RenderQualitySection quality={quality} onChange={setQuality} />

      {planError ? (
        <p role="alert" className="text-xs text-error">
          {planError}
        </p>
      ) : null}

      <SpecListSection
        specs={specs}
        lifecycles={lifecycles}
        onRender={handleRenderSpec}
        onSkip={(id) =>
          setSpecs((prev) => prev.filter((s) => s.id !== id))
        }
        focusSectionIndex={focusSectionIndex ?? null}
      />
    </aside>
  );
}

function PanelHeader({
  specCount,
  renderedCount,
  totalCost,
  breakdown,
  onClose,
}: {
  specCount: number;
  renderedCount: number;
  totalCost: number;
  breakdown: { provider: string; count: number; usd: number }[];
  onClose?: () => void;
}) {
  return (
    <header className="flex items-start justify-between">
      <div className="flex flex-col gap-1">
        <h2 className="text-xl font-heading font-semibold text-neutral-900">
          Visual Studio
        </h2>
        <p className="text-xs text-neutral-500">
          {specCount} specs · {renderedCount} rendered
        </p>
        <p className="mt-1 text-xs text-neutral-500">
          Plan, generate, and refine. Every visual stays linked to its section.
        </p>
      </div>
      <div className="flex items-center gap-2">
        <UsageBadge totalUsd={totalCost} breakdown={breakdown} />
        {onClose ? (
          <button
            type="button"
            onClick={onClose}
            aria-label="Close Visual Studio"
            className="rounded-md p-1 text-neutral-500 hover:bg-neutral-100"
          >
            <span aria-hidden="true">×</span>
          </button>
        ) : null}
      </div>
    </header>
  );
}

function PageArtDirectionField({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      <label
        htmlFor="page-art-direction"
        className="text-xs font-medium uppercase tracking-wide text-neutral-500"
      >
        Page art direction
      </label>
      <textarea
        id="page-art-direction"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="e.g. soft natural light, slate palette, no people, editorial composition"
        rows={3}
        className="rounded-md border border-neutral-200 px-3 py-2 text-sm text-neutral-900 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
      />
    </div>
  );
}

function DefaultStyleSection({
  styles,
  selected,
  onSelect,
}: {
  styles: VisualStylesResponse["styles"];
  selected: string | null;
  onSelect: (key: string | null) => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      <label className="text-xs font-medium uppercase tracking-wide text-neutral-500">
        Default visual style
      </label>
      {styles.length === 0 ? (
        <p className="text-xs text-neutral-400">Loading catalogue…</p>
      ) : (
        <StyleChipRail
          styles={styles}
          selected={selected}
          onSelect={onSelect}
        />
      )}
    </div>
  );
}

function RenderQualitySection({
  quality,
  onChange,
}: {
  quality: RenderQuality;
  onChange: (q: RenderQuality) => void;
}) {
  const tiers: RenderQuality[] = ["standard", "fast", "mid", "premium"];
  return (
    <div className="flex flex-col gap-2">
      <label className="text-xs font-medium uppercase tracking-wide text-neutral-500">
        Render quality
      </label>
      <div className="grid grid-cols-2 gap-2">
        {tiers.map((tier) => {
          const isSelected = tier === quality;
          return (
            <button
              key={tier}
              type="button"
              onClick={() => onChange(tier)}
              aria-pressed={isSelected}
              className={cn(
                "flex flex-col items-start rounded-md border px-3 py-2 text-left transition-colors",
                isSelected
                  ? "border-primary bg-primary-light text-primary"
                  : "border-neutral-200 bg-white text-neutral-700 hover:bg-neutral-50",
              )}
            >
              <span className="text-xs font-medium">
                {QUALITY_LABELS[tier]}
              </span>
              <span className="text-xs text-neutral-500">
                {QUALITY_TO_PROVIDER[tier]}
              </span>
              <span className="mt-1 text-xs font-mono text-neutral-700">
                ${QUALITY_PRICE_USD[tier].toFixed(3)} / img
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function SpecListSection({
  specs,
  lifecycles,
  onRender,
  onSkip,
  focusSectionIndex,
}: {
  specs: ImageSpec[];
  lifecycles: Record<string, SpecLifecycle>;
  onRender: (spec: ImageSpec) => void;
  onSkip: (id: string) => void;
  focusSectionIndex?: number | null;
}) {
  if (specs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 rounded-md border border-dashed border-neutral-300 bg-neutral-50 p-6 text-sm text-neutral-500">
        <span className="font-medium">No specs yet</span>
        <span className="text-xs">
          Click <strong>Plan visuals</strong> to generate ImageSpecs for this
          article.
        </span>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-xs font-medium uppercase tracking-wide text-neutral-500">
        Spec list · {specs.length} planned
      </h3>
      {specs.map((spec) => {
        const lc = lifecycles[spec.id] ?? { state: "idle", render: null };
        const specSectionIndex = spec.placement.section_index;
        const isFocused =
          focusSectionIndex != null && specSectionIndex === focusSectionIndex;
        return (
          <div
            key={spec.id}
            data-section-index={specSectionIndex}
            className={cn(
              "rounded-md transition-shadow",
              isFocused &&
                "ring-2 ring-primary ring-offset-2 ring-offset-white",
            )}
          >
            <SpecCard
              spec={spec}
              state={lc.state}
              render={lc.render}
              errorMessage={lc.error}
              onPlan={() => onRender(spec)}
              onRegenerate={() => onRender(spec)}
              onRetryCheaper={() => onRender(spec)}
              onSkip={() => onSkip(spec.id)}
            />
          </div>
        );
      })}
    </div>
  );
}
