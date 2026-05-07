import { apiClient } from "./client";
import type {
  FetchUrlRequest,
  FetchUrlResponse,
  PlanRequest,
  PlanResponse,
  RenderRequest,
  RenderResponse,
  SectionHtmlRefineRequest,
  SectionHtmlRefineResponse,
  UploadResponse,
  VisualStylesResponse,
} from "@/types/visuals";

/**
 * Visual Studio HTTP client (Phase 5 / VISUAL-008).
 *
 * Mirrors `src/api/routers/visuals.py`. Every mutating call is auth-gated
 * (the request interceptor in `client.ts` attaches the bearer) and
 * server-side rate-limited.
 */

export async function fetchVisualStyles(): Promise<VisualStylesResponse> {
  const { data } = await apiClient.get<VisualStylesResponse>("/visuals/styles");
  return data;
}

export async function planVisuals(body: PlanRequest): Promise<PlanResponse> {
  const { data } = await apiClient.post<PlanResponse>("/visuals/plan", body);
  return data;
}

export async function renderSpec(body: RenderRequest): Promise<RenderResponse> {
  const { data } = await apiClient.post<RenderResponse>(
    "/visuals/render",
    body,
  );
  return data;
}

export async function uploadBrandAsset(
  file: File,
  label?: string,
): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  if (label) {
    form.append("label", label);
  }
  const { data } = await apiClient.post<UploadResponse>(
    "/visuals/upload",
    form,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return data;
}

export async function fetchImageFromUrl(
  body: FetchUrlRequest,
): Promise<FetchUrlResponse> {
  const { data } = await apiClient.post<FetchUrlResponse>(
    "/visuals/fetch-from-url",
    body,
  );
  return data;
}

export async function refineSectionHtml(
  body: SectionHtmlRefineRequest,
): Promise<SectionHtmlRefineResponse> {
  const { data } = await apiClient.post<SectionHtmlRefineResponse>(
    "/visuals/section-html-refine",
    body,
  );
  return data;
}
