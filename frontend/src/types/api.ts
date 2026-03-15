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
