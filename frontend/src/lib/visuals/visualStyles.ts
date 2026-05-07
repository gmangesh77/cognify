import { fetchVisualStyles } from "@/lib/api/visuals";
import type { VisualStylesResponse } from "@/types/visuals";

/**
 * Boot-time fetch + module-local cache for the Visual Style catalogue.
 *
 * The backend (`/api/v1/visuals/styles`) is the single source of truth for
 * styles, personas, and the banned-cliché block (ADR-005). The frontend
 * never mirrors this catalogue in TypeScript — we cache the response on
 * first read and return it from memory thereafter.
 */

let _cache: VisualStylesResponse | null = null;
let _inflight: Promise<VisualStylesResponse> | null = null;

export async function getVisualStylesCached(): Promise<VisualStylesResponse> {
  if (_cache) return _cache;
  if (!_inflight) {
    _inflight = fetchVisualStyles().then((res) => {
      _cache = res;
      _inflight = null;
      return res;
    });
  }
  return _inflight;
}

export function resetVisualStylesCache(): void {
  _cache = null;
  _inflight = null;
}

export function getCachedVisualStyles(): VisualStylesResponse | null {
  return _cache;
}
