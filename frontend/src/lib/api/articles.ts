import { apiClient } from "./client";

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
  }[];
  provenance: {
    research_session_id: string;
    primary_model: string;
    drafting_model: string;
    embedding_model: string;
    embedding_version: string;
  };
  authors: string[];
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
): Promise<PaginatedArticles> {
  const { data } = await apiClient.get<PaginatedArticles>("/articles", {
    params: { page, size },
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
