export interface LlmCallResponse {
  id: string;
  step_id: string | null;
  call_name: string;
  model_name: string;
  prompt_messages: Array<{ role: string; content: string }>;
  response_content: string;
  input_tokens: number | null;
  output_tokens: number | null;
  duration_ms: number | null;
  error: string | null;
  started_at: string;
  completed_at: string | null;
}

export interface DebugStepResponse {
  id: string;
  step_name: string;
  status: string;
  input_data: Record<string, unknown>;
  output_data: Record<string, unknown>;
  duration_ms: number | null;
  started_at: string;
  completed_at: string | null;
  llm_calls: LlmCallResponse[];
}

export interface PipelineDebugResponse {
  session_id: string;
  topic_title: string;
  topic_domain: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
  target_audience: string | null;
  content_tone: string | null;
  preferred_angle: string | null;
  steps: DebugStepResponse[];
  total_llm_calls: number;
  total_input_tokens: number;
  total_output_tokens: number;
}

export interface DebugSessionSummary {
  session_id: string;
  topic_title: string;
  status: string;
  started_at: string;
  duration_seconds: number | null;
  step_count: number;
  llm_call_count: number;
}

export interface PaginatedDebugSessions {
  items: DebugSessionSummary[];
  total: number;
  page: number;
  size: number;
}
