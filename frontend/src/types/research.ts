export type SessionStatus =
  | "planning"
  | "in_progress"
  | "researching"
  | "evaluating"
  | "running"
  | "complete"
  | "completed"
  | "awaiting_outline_review"
  | "generating_article"
  | "article_complete"
  | "article_failed"
  | "cancelled"
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
  require_outline_approval?: boolean;
}

export interface OutlineSection {
  index: number;
  title: string;
  description: string;
  key_points: string[];
  target_word_count: number;
  relevant_facets: number[];
}

export interface ArticleOutline {
  title: string;
  subtitle: string | null;
  content_type: string;
  sections: OutlineSection[];
  total_target_words: number;
  reasoning: string;
}

export interface OutlineResponse {
  draft_id: string;
  session_id: string;
  status: string;
  outline: ArticleOutline;
}

export interface SessionActionResponse {
  session_id: string;
  status: string;
}

export interface PaginatedResearchSessions {
  items: ResearchSessionSummary[];
  total: number;
  page: number;
  size: number;
}

export type SessionEventType =
  | "snapshot"
  | "status_changed"
  | "step_started"
  | "step_progress"
  | "step_done"
  | "step_failed"
  | "done"
  | "error"
  | "keepalive";

export interface SessionStepRow {
  id: string;
  step_name: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  duration_ms: number | null;
  output_data: Record<string, unknown>;
}

export interface SessionEvent {
  type: SessionEventType;
  session_id: string;
  status: string | null;
  step: string | null;
  data: Record<string, unknown>;
  ts: string;
}
