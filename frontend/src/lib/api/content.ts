import { apiClient } from "./client";
import type {
  HumanizePreviewRequest,
  HumanizePreviewResponse,
  ParagraphToneRequest,
  SectionHistoryResponse,
  SectionRegenerateRequest,
  SectionRegenerateResponse,
  SectionRestoreRequest,
  SectionRewriteRequest,
  SectionRewriteResponse,
  SectionUpdateRequest,
  SectionUpdateResponse,
} from "@/types/content";

/**
 * Per-section content editing client (VISUAL-011 / Phase 8).
 *
 * Mirrors `src/api/routers/content.py`. Every call is auth-gated by the
 * shared bearer interceptor in `client.ts` and server-side rate-limited.
 */

export async function rewriteSectionProse(
  body: SectionRewriteRequest,
): Promise<SectionRewriteResponse> {
  const { data } = await apiClient.post<SectionRewriteResponse>(
    "/content/section-rewrite",
    body,
  );
  return data;
}

export async function applyTonePreset(
  body: ParagraphToneRequest,
): Promise<SectionRewriteResponse> {
  const { data } = await apiClient.post<SectionRewriteResponse>(
    "/content/paragraph-tone",
    body,
  );
  return data;
}

export async function persistSectionUpdate(
  body: SectionUpdateRequest,
): Promise<SectionUpdateResponse> {
  const { data } = await apiClient.post<SectionUpdateResponse>(
    "/content/section-update",
    body,
  );
  return data;
}

export async function fetchSectionHistory(
  sectionId: string,
  limit = 50,
): Promise<SectionHistoryResponse> {
  const { data } = await apiClient.get<SectionHistoryResponse>(
    `/content/section/${encodeURIComponent(sectionId)}/history`,
    { params: { limit } },
  );
  return data;
}

export async function previewHumanization(
  body: HumanizePreviewRequest,
): Promise<HumanizePreviewResponse> {
  const { data } = await apiClient.post<HumanizePreviewResponse>(
    "/content/humanize-preview",
    body,
  );
  return data;
}

export async function restoreSectionVersion(
  sectionId: string,
  body: SectionRestoreRequest,
): Promise<SectionUpdateResponse> {
  const { data } = await apiClient.post<SectionUpdateResponse>(
    `/content/section/${encodeURIComponent(sectionId)}/restore`,
    body,
  );
  return data;
}

/** AUTHOR-004 — redraft one section; returns a candidate + diff (body untouched). */
export async function regenerateSection(
  body: SectionRegenerateRequest,
): Promise<SectionRegenerateResponse> {
  const { data } = await apiClient.post<SectionRegenerateResponse>(
    "/content/section-regenerate",
    body,
  );
  return data;
}

/**
 * Stable section identifier used by the toolbar + drawer + popover.
 * `sectionIndex` is the 0-based H2 (outline) index — the same space the
 * backend's `make_section_id` uses since AUTHOR-004 (L-013). Never add
 * an offset for the prelude here; `SectionHistoryService` converts to
 * `split_sections` indices internally.
 */
export function makeSectionId(articleId: string, sectionIndex: number): string {
  return `${articleId}:${sectionIndex}`;
}
