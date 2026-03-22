import { apiClient } from "./client";

// ---------------------------------------------------------------------------
// Backend-shaped types (mirror src/api/schemas/topics.py + trends.py)
// ---------------------------------------------------------------------------

export interface BackendRawTopic {
  title: string;
  description: string;
  source: string;
  external_url: string;
  trend_score: number;
  discovered_at: string;
  velocity: number;
  domain_keywords: string[];
}

export interface BackendRankedTopic extends BackendRawTopic {
  composite_score: number;
  rank: number;
  source_count: number;
}

export interface TrendFetchRequest {
  domain_keywords: string[];
  max_results?: number;
  sources?: string[] | null;
}

export interface SourceResult {
  source_name: string;
  topics: BackendRawTopic[];
  topic_count: number;
  duration_ms: number;
  error: string | null;
}

export interface TrendFetchResponse {
  topics: BackendRawTopic[];
  sources_queried: string[];
  source_results: Record<string, SourceResult>;
}

export interface RankTopicsRequest {
  topics: BackendRawTopic[];
  domain: string;
  domain_keywords?: string[];
  top_n?: number;
}

export interface RankTopicsResponse {
  ranked_topics: BackendRankedTopic[];
  duplicates_removed: unknown[];
  total_input: number;
  total_after_dedup: number;
  total_returned: number;
}

export interface PersistTopicsRequest {
  ranked_topics: BackendRankedTopic[];
  domain: string;
}

export interface PersistTopicsResponse {
  new_count: number;
  updated_count: number;
  total_persisted: number;
}

export interface PersistedTopic {
  id: string;
  title: string;
  description: string;
  source: string;
  external_url: string;
  trend_score: number;
  velocity: number;
  domain: string;
  discovered_at: string;
  composite_score: number | null;
  rank: number | null;
  source_count: number;
  created_at: string;
  updated_at: string;
}

export interface PaginatedTopics {
  items: PersistedTopic[];
  total: number;
  page: number;
  size: number;
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export async function fetchTrends(req: TrendFetchRequest): Promise<TrendFetchResponse> {
  const { data } = await apiClient.post<TrendFetchResponse>("/trends/fetch", req);
  return data;
}

export async function rankTopics(req: RankTopicsRequest): Promise<RankTopicsResponse> {
  const { data } = await apiClient.post<RankTopicsResponse>("/topics/rank", req);
  return data;
}

export async function persistTopics(req: PersistTopicsRequest): Promise<PersistTopicsResponse> {
  const { data } = await apiClient.post<PersistTopicsResponse>("/topics/persist", req);
  return data;
}

export async function fetchPersistedTopics(domain: string, page = 1, size = 20): Promise<PaginatedTopics> {
  const { data } = await apiClient.get<PaginatedTopics>("/topics", { params: { domain, page, size } });
  return data;
}

export interface CreateSessionResponse {
  session_id: string;
  status: string;
  started_at: string;
}

export async function createResearchSession(topicId: string): Promise<CreateSessionResponse> {
  const { data } = await apiClient.post<CreateSessionResponse>("/research/sessions", {
    topic_id: topicId,
  });
  return data;
}
