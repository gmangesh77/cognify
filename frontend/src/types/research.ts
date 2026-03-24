export type SessionStatus =
  | "planning"
  | "in_progress"
  | "complete"
  | "generating_article"
  | "article_complete"
  | "article_failed"
  | "failed";

export interface AgentStep {
  step_name: string;
  status: string;
  duration_ms: number | null;
  started_at: string;
  completed_at: string | null;
  output_summary: string | null;
}

export interface ResearchSessionSummary {
  session_id: string;
  topic_id: string;
  status: SessionStatus;
  round_count: number;
  findings_count: number;
  sources_count: number;
  embeddings_count: number;
  topic_title: string;
  duration_seconds: number | null;
  started_at: string;
}

export interface ResearchSessionDetail extends ResearchSessionSummary {
  completed_at: string | null;
  steps: AgentStep[];
}

export interface PaginatedResearchSessions {
  items: ResearchSessionSummary[];
  total: number;
  page: number;
  size: number;
}
