import type {
  ImageSpec,
  RenderResponse,
  SpecCardState,
} from "@/types/visuals";

/**
 * Visual Studio state contracts + pure helpers (INFRA-008 split from
 * `components/visuals/VisualStudio.tsx`). No React here — everything is
 * unit-testable without rendering.
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

export interface InsertedVisual {
  spec: ImageSpec;
  render: RenderResponse;
}

export interface SpecLifecycle {
  state: SpecCardState;
  render: RenderResponse | null;
  error?: string;
}

export interface ProviderBreakdown {
  provider: string;
  count: number;
  usd: number;
}

export function idleLifecycles(
  specs: ImageSpec[],
): Record<string, SpecLifecycle> {
  return Object.fromEntries(
    specs.map((s) => [s.id, { state: "idle", render: null }]),
  );
}

export function totalCostOf(
  lifecycles: Record<string, SpecLifecycle>,
): number {
  return Object.values(lifecycles).reduce(
    (sum, lc) => sum + (lc.render?.cost_usd ?? 0),
    0,
  );
}

export function breakdownOf(
  lifecycles: Record<string, SpecLifecycle>,
): ProviderBreakdown[] {
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
}

export function readyVisualsOf(
  specs: ImageSpec[],
  lifecycles: Record<string, SpecLifecycle>,
): InsertedVisual[] {
  const ready: InsertedVisual[] = [];
  for (const spec of specs) {
    const lc = lifecycles[spec.id];
    if (lc?.state === "done" && lc.render) ready.push({ spec, render: lc.render });
  }
  return ready;
}
