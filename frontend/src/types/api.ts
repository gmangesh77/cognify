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
  status: "live" | "draft" | "scheduled" | "failed";
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
