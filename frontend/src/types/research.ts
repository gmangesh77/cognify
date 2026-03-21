export type SessionStatus = "planning" | "in_progress" | "complete" | "failed";

export interface AgentStep {
  step_name: string;
  status: string;
  duration_ms: number | null;
  started_at: string;
  completed_at: string | null;
}

export interface ResearchSessionSummary {
  session_id: string;
  topic_id: string;
  status: SessionStatus;
  round_count: number;
  findings_count: number;
  started_at: string;
  // Frontend-only fields populated in mock data:
  topic_title?: string; // TODO: backend doesn't return this — extend API or join client-side
  duration_seconds?: number | null; // TODO: backend only returns this in detail response
}

export interface ResearchSessionDetail extends ResearchSessionSummary {
  duration_seconds: number | null;
  completed_at: string | null;
  steps: AgentStep[];
}

export interface PaginatedResearchSessions {
  items: ResearchSessionSummary[];
  total: number;
  page: number;
  size: number;
}
