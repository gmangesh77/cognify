import type { PersistedTopic } from "@/lib/api/trends";

export interface RawTopic {
  title: string;
  description: string;
  source: string;
  external_url: string;
  trend_score: number;
  discovered_at: string;
  velocity: number;
  domain_keywords: string[];
}

export interface RankedTopic extends RawTopic {
  id?: string;
  composite_score: number;
  rank: number;
  source_count: number;
  domain: string;
  trend_status: "trending" | "new" | "rising" | "steady";
}

export interface DashboardMetrics {
  topics_discovered: { value: number; trend: number; direction: "up" | "down" };
  articles_generated: { value: number; trend: number; direction: "up" | "down" };
  avg_research_time: { value: string; trend: number; direction: "up" | "down" };
  published: { value: number; trend: number; direction: "up" | "down" };
}

export interface Article {
  id: string;
  title: string;
  status: "live" | "draft" | "scheduled" | "failed" | "complete";
  published_at: string;
  views: number;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    details: string[];
  };
}

export type TimeRange = "1h" | "24h" | "7d" | "30d" | "all";

export interface TopicFilters {
  sources: string[];
  timeRange: TimeRange;
  domain: string;
}

export interface ScanState {
  isScanning: boolean;
  completedSources: number;
  totalSources: number;
  failedSources: string[];
}

export interface GenerateArticleResponse {
  task_id: string;
  status: "queued";
  estimated_time_seconds: number;
}

export interface TopicAnalysisResult {
  description: string;
  domain: string;
  keywords: string[];
  target_audience: string;
  content_tone: string;
  preferred_angle: string;
}

export interface AnalyzeTopicRequest {
  title: string;
  regenerate_field?: string | null;
  current_values?: TopicAnalysisResult | null;
}

export interface ManualTopicCreateRequest {
  title: string;
  description: string;
  domain: string;
  keywords: string[];
  force_create?: boolean;
}

export interface ManualTopicResult {
  topic: PersistedTopic;
  is_duplicate: boolean;
  duplicate_of: string | null;
}

export type ContentTone =
  | "technical-authoritative"
  | "conversational"
  | "educational"
  | "analytical"
  | "news-reporting";

export type StructuralDiagramMode = "illustration" | "mermaid";

export interface ArticleParams {
  target_audience?: string;
  content_tone?: ContentTone;
  preferred_angle?: string;
  keywords?: string[];
  topic_description_override?: string;
  /** How structural diagrams are rendered: AI illustration vs Mermaid. */
  structural_diagram_mode?: StructuralDiagramMode;
}
