import type { RenderResponse } from "@/types/visuals";

/**
 * URL-first image source picker (Phase 5 / VISUAL-008).
 *
 * Mirrors impactai's `pickGeneratedImageSrc` helper. The backend's
 * `/visuals/render` endpoint returns either a public URL (MinIO is
 * configured) OR a base64-encoded payload (LocalDisk fallback in dev).
 * Both modes need to render in the same `<img>` slot — this helper picks
 * whichever is present and converts the base64 case to a data URL.
 */
export function pickGeneratedImageSrc(
  result: Pick<RenderResponse, "image_url" | "image_base64" | "mime_type">,
): string | null {
  if (result.image_url) return result.image_url;
  if (result.image_base64) {
    const mime = result.mime_type || "image/png";
    return `data:${mime};base64,${result.image_base64}`;
  }
  return null;
}

/**
 * Pull a render-time URL from a stored ImageAsset (the `metadata` shape
 * the backend persists). Useful when the frontend lazy-loads existing
 * article visuals without re-rendering.
 */
export function pickAssetUrl(asset: {
  url: string | null;
  metadata?: Record<string, unknown> | null;
}): string | null {
  if (asset.url) return asset.url;
  return null;
}
