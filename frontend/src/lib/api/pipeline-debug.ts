import { apiClient } from "@/lib/api/client";
import type {
  PaginatedDebugSessions,
  PipelineDebugResponse,
  LlmCallResponse,
} from "@/types/pipeline-debug";

export async function fetchDebugSessions(
  page = 1,
  size = 20,
): Promise<PaginatedDebugSessions> {
  const { data } = await apiClient.get<PaginatedDebugSessions>(
    "/debug/sessions",
    { params: { page: String(page), size: String(size) } },
  );
  return data;
}

export async function fetchPipelineDebug(
  sessionId: string,
): Promise<PipelineDebugResponse> {
  const { data } = await apiClient.get<PipelineDebugResponse>(
    `/debug/sessions/${sessionId}`,
  );
  return data;
}

export async function fetchSessionLlmCalls(
  sessionId: string,
): Promise<LlmCallResponse[]> {
  const { data } = await apiClient.get<LlmCallResponse[]>(
    `/debug/sessions/${sessionId}/llm-calls`,
  );
  return data;
}
