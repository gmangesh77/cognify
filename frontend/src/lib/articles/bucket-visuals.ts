import type { ImageAsset } from "@/types/articles";

export interface BucketedVisuals {
  overviewDiagrams: ImageAsset[];
  sectionDiagrams: Map<number, ImageAsset[]>;
  coverImage: ImageAsset | null;
  sectionImages: Map<number, ImageAsset[]>;
}

export function isDiagramVisual(v: ImageAsset): boolean {
  return Boolean(v.metadata?.diagram_type && v.metadata?.mermaid_syntax);
}

/**
 * Section index for any visual: the planner stamps `section_index`,
 * legacy charts/diagrams use `source_section`. Read both.
 */
export function sectionIndexOf(v: ImageAsset): number | null {
  const meta = v.metadata ?? {};
  const raw = meta.section_index ?? meta.source_section;
  if (raw === undefined || raw === null) return null;
  const n = typeof raw === "number" ? raw : Number.parseInt(String(raw), 10);
  return Number.isFinite(n) ? n : null;
}

function push(map: Map<number, ImageAsset[]>, idx: number, asset: ImageAsset): void {
  const bucket = map.get(idx) ?? [];
  bucket.push(asset);
  map.set(idx, bucket);
}

/**
 * Bucket non-diagram images:
 *   * placement_anchor === "cover"  → article cover (rendered once at top)
 *   * else use section_index (new planner) OR source_section (legacy)
 *   * sections < 0 fall back to the cover slot
 * Only the FIRST cover-candidate wins — multiple heroes are not stacked.
 */
export function bucketVisuals(visuals: ImageAsset[]): BucketedVisuals {
  const diagrams = visuals.filter(isDiagramVisual);
  const images = visuals.filter((v) => !isDiagramVisual(v));
  const sectionDiagrams = new Map<number, ImageAsset[]>();
  for (const d of diagrams) {
    const idx = sectionIndexOf(d);
    if (idx !== null && idx >= 0) push(sectionDiagrams, idx, d);
  }
  let coverImage: ImageAsset | null = null;
  const sectionImages = new Map<number, ImageAsset[]>();
  for (const img of images) {
    const anchor = img.metadata?.placement_anchor;
    const role = img.metadata?.role_style;
    const idx = sectionIndexOf(img);
    const isCoverCandidate =
      anchor === "cover" || (anchor == null && idx == null && role === "hero");
    if (isCoverCandidate) {
      if (coverImage == null) coverImage = img; // first cover wins; ignore extra heroes
      continue;
    }
    if (idx !== null && idx >= 0) push(sectionImages, idx, img);
    else if (coverImage == null) coverImage = img; // unanchored non-hero — last-resort cover
  }
  return {
    overviewDiagrams: diagrams.filter((d) => sectionIndexOf(d) === -1),
    sectionDiagrams,
    coverImage,
    sectionImages,
  };
}
