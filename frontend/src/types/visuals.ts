/**
 * TypeScript mirrors of the Pydantic models exposed by the Visual Studio
 * API (Phase 4 / VISUAL-007). Single source of truth for the catalogue,
 * personas, and cliché block lives in the backend and is fetched at boot
 * via `GET /api/v1/visuals/styles` — see `frontend/src/lib/visuals/visualStyles.ts`.
 */

export type ImageRoleStyle =
  | "hero"
  | "feature_card"
  | "concept"
  | "process_step"
  | "comparison_split"
  | "quote_card"
  | "stat_card"
  | "screenshot_mock"
  | "editorial"
  | "background";

export type ImageAspectRatio = "16:9" | "1:1" | "4:3" | "3:4" | "4:5";

export type PlacementAnchor =
  | "cover"
  | "top"
  | "before_heading"
  | "between_paragraphs"
  | "bottom_grid"
  | "background"
  | "column_split";

export type ImageProviderKey =
  | "gemini_flash"
  | "gemini_3_pro"
  | "imagen_4"
  | "dalle_3";

export interface ImagePlacement {
  anchor: PlacementAnchor;
  heading_text: string | null;
  paragraph_index: number | null;
  section_index: number;
}

export interface ImageSpec {
  id: string;
  role_style: ImageRoleStyle;
  visual_style: string | null;
  prompt: string;
  alt_text: string;
  aspect_ratio: ImageAspectRatio;
  placement: ImagePlacement;
  rationale: string | null;
  provider: ImageProviderKey | null;
}

export interface StyleCatalogueEntry {
  key: string;
  label: string;
  category: "photo" | "illustration" | "editorial" | "technical";
  default_aspect: ImageAspectRatio;
  short_desc: string;
  prompt_fragment: string;
}

export interface PersonaEntry {
  key: string;
  direction: string;
}

export interface VisualStylesResponse {
  styles: StyleCatalogueEntry[];
  role_defaults: Record<string, string>;
  personas: PersonaEntry[];
  default_persona: string;
  banned_cliches_block: string;
  planner_catalogue_block: string;
}

export interface PlanRequest {
  topic: { title: string; description: string; domain: string };
  section?: {
    section_index: number;
    title: string;
    body_markdown: string;
  };
  article_summary: string;
  page_art_direction?: string | null;
  audience_persona?: string | null;
  target_audience?: string | null;
  brand_context?: string | null;
  max_images_per_section?: number;
  plan_cover?: boolean;
}

export interface PlanResponse {
  cover: ImageSpec | null;
  section_specs: ImageSpec[];
}

export interface RenderRequest {
  spec: ImageSpec;
  page_direction?: string | null;
  section_override?: string | null;
  refine_note?: string | null;
  prompt_override?: string | null;
  provider?: ImageProviderKey | null;
}

export interface RenderResponse {
  image_url: string | null;
  image_base64: string | null;
  spec_id: string;
  width: number;
  height: number;
  mime_type: string;
  provider: string;
  model: string;
  cost_usd: number | null;
  latency_ms: number;
}

export interface UploadResponse {
  image_url: string | null;
  object_key: string;
  size_bytes: number;
  mime_type: string;
}

export interface FetchUrlRequest {
  url: string;
}

export interface FetchUrlResponse {
  image_url: string | null;
  object_key: string;
  final_url: string;
  mime_type: string;
  size_bytes: number;
}

export interface SectionHtmlRefineRequest {
  section_id: string;
  instruction: string;
  current_html: string;
}

export interface SectionHtmlRefineResponse {
  section_id: string;
  html_fragment: string;
  model: string;
  prompt_used: string;
}

/**
 * Lifecycle states for a SpecCard. See Pencil Screen 2 (`pb0Hz`):
 * idle → planning → generating → done, with `error` and `refining`
 * branches reachable from `done` or `generating`.
 */
export type SpecCardState =
  | "idle"
  | "planning"
  | "generating"
  | "done"
  | "error"
  | "refining";

/**
 * Render-quality tier (Pencil Screen 1 — "Render quality" sub-section).
 * Drives the chosen provider for /visuals/render calls.
 */
export type RenderQuality = "fast" | "mid" | "premium";

export const QUALITY_TO_PROVIDER: Record<RenderQuality, ImageProviderKey> = {
  fast: "gemini_flash",
  mid: "gemini_3_pro",
  premium: "imagen_4",
};

export const QUALITY_LABELS: Record<RenderQuality, string> = {
  fast: "Fast",
  mid: "Mid",
  premium: "Premium",
};

/**
 * Approximate per-image cost shown on the quality tier picker. Pulled from
 * the implementation plan §5.2 cost table; the live cost-tracking endpoint
 * (`GET /visuals/cost`) is the authoritative source for actual usage.
 */
export const QUALITY_PRICE_USD: Record<RenderQuality, number> = {
  fast: 0.001,
  mid: 0.015,
  premium: 0.04,
};

export interface SavedAssetItem {
  spec_id: string;
  article_id: string;
  article_title: string;
  image_url: string;
  role_style: string;
  visual_style: string | null;
  aspect_ratio: string;
  provider: string;
  cost_usd: number | null;
  generated_at: string;
  alt_text: string | null;
  caption: string | null;
}

export interface SavedAssetFacets {
  by_article: Record<string, number>;
  by_provider: Record<string, number>;
  by_role_style: Record<string, number>;
}

export interface SavedAssetsResponse {
  items: SavedAssetItem[];
  facets: SavedAssetFacets;
  total_count: number;
  total_spend_usd: number;
}

export interface SavedAssetsQuery {
  role_style?: string | null;
  provider?: string | null;
  article_id?: string | null;
  limit?: number;
}
