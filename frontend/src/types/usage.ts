export interface UsageByOperation {
  op: string;
  llm_calls: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
}

export interface UsageSummary {
  session_id: string;
  llm_calls: number;
  input_tokens: number;
  output_tokens: number;
  images: number;
  cost_usd: number;
  by_operation: UsageByOperation[];
}
