import { apiClient } from "./client";
import type {
  ArticleMetadataPatch,
  ArticleMetadataResult,
  SeoRegenerateField,
  SeoRegenerateResult,
} from "@/types/articles";
import type { UsageSummary } from "@/types/usage";

export interface ArticleResponse {
  id: string;
  title: string;
  subtitle: string | null;
  body_markdown: string;
  summary: string;
  key_claims: string[];
  content_type: string;
  domain: string;
  ai_generated: boolean;
  generated_at: string;
  seo: {
    title: string;
    description: string;
    keywords: string[];
    canonical_url: string | null;
    structured_data: {
      headline: string;
      description: string;
      keywords: string[];
      date_published: string;
      date_modified: string;
    } | null;
  };
  citations: {
    index: number;
    title: string;
    url: string;
    authors: string[];
    published_at: string | null;
  }[];
  visuals: {
    id: string;
    url: string;
    caption: string | null;
    alt_text: string | null;
    metadata: {
      diagram_type?: string;
      source_section?: number;
      mermaid_syntax?: string;
      section_index?: number;
      placement_anchor?: string;
      role_style?: string;
    } | null;
  }[];
  provenance: {
    research_session_id: string;
    primary_model: string;
    drafting_model: string;
    embedding_model: string;
    embedding_version: string;
  };
  authors: string[];
  status?: string; // AUTHOR-007 editorial state (optional: older fixtures)
  // AUTHOR-011 persona voice engine fields.
  audience_persona?: string | null;
  voice_persona_id?: string | null;
  voice_match_score?: number | null;
  voice_scores_by_section?: Record<string, number> | null;
  few_shot_sample_ids?: string[];
}

export interface PaginatedArticles {
  items: ArticleResponse[];
  total: number;
  page: number;
  size: number;
}

export async function fetchArticles(
  page = 1,
  size = 20,
  status?: string,
): Promise<PaginatedArticles> {
  const params: Record<string, string | number> = { page, size };
  if (status) params.status = status;
  const { data } = await apiClient.get<PaginatedArticles>("/articles", {
    params,
  });
  return data;
}

export async function fetchArticle(
  id: string,
): Promise<ArticleResponse> {
  const { data } = await apiClient.get<ArticleResponse>(`/articles/${id}`);
  return data;
}

export interface PublishResult {
  article_id: string;
  platform: string;
  status: string;
  external_id: string | null;
  external_url: string | null;
  published_at: string | null;
  error_message: string | null;
}

export async function publishArticle(
  articleId: string,
  platform: string,
): Promise<PublishResult> {
  const { data } = await apiClient.post<PublishResult>(
    `/articles/${articleId}/publish`,
    { platform },
  );
  return data;
}

export interface AttachVisualPayload {
  url: string;
  caption?: string | null;
  alt_text?: string | null;
  metadata?: Record<string, string | number | null> | null;
}

/**
 * Persist a Visual Studio render onto an existing article so it appears
 * on subsequent fetches and is included in publishes.
 */
export async function attachVisualToArticle(
  articleId: string,
  payload: AttachVisualPayload,
): Promise<ArticleResponse> {
  const { data } = await apiClient.post<ArticleResponse>(
    `/articles/${articleId}/visuals`,
    payload,
  );
  return data;
}

export async function fetchArticleUsage(
  articleId: string,
): Promise<UsageSummary> {
  const { data } = await apiClient.get<UsageSummary>(
    `/articles/${articleId}/usage`,
  );
  return data;
}

export async function patchArticleMetadata(
  articleId: string,
  patch: ArticleMetadataPatch,
): Promise<ArticleMetadataResult> {
  const { data } = await apiClient.patch<ArticleMetadataResult>(
    `/articles/${articleId}`,
    patch,
  );
  return data;
}

export async function regenerateSeoField(
  articleId: string,
  field: SeoRegenerateField,
): Promise<SeoRegenerateResult> {
  const { data } = await apiClient.post<SeoRegenerateResult>(
    `/articles/${articleId}/seo/regenerate`,
    { field },
  );
  return data;
}
