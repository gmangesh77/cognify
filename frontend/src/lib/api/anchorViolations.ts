import type { AnchorViolationEntry } from "@/types/content";

type AxiosLike = {
  response?: {
    status?: number;
    data?: { detail?: { violations?: AnchorViolationEntry[] } };
  };
};

/**
 * Parse the backend's 422 `{"error":"anchor_violation","violations":[…]}`
 * payload (built by `content_shared.anchor_violation_http`). Single source
 * of truth for the inline editor, the regenerate hook and the popover.
 */
export function extractAnchorViolations(err: unknown): AnchorViolationEntry[] {
  const e = err as AxiosLike;
  if (e?.response?.status !== 422) return [];
  return e.response.data?.detail?.violations ?? [];
}
