export type PublicationStatus = "success" | "failed" | "scheduled";

export interface PublicationEvent {
  timestamp: string;
  status: PublicationStatus;
  error_message: string | null;
}

export interface Publication {
  id: string;
  article_id: string;
  article_title: string;
  platform: string;
  status: PublicationStatus;
  external_id: string | null;
  external_url: string | null;
  published_at: string | null;
  view_count: number;
  seo_score: number;
  error_message: string | null;
  event_history: PublicationEvent[];
  created_at: string;
  updated_at: string;
}

export interface PublicationListResponse {
  items: Publication[];
  total: number;
  page: number;
  size: number;
}

export interface PlatformSummary {
  platform: string;
  total: number;
  success: number;
  failed: number;
  scheduled: number;
}
