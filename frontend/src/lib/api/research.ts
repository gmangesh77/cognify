import axios from "axios";
import { apiClient } from "@/lib/api/client";
import type {
  ArticleOutline,
  OutlineResponse,
  PaginatedResearchSessions,
  ResearchSessionDetail,
  SessionActionResponse,
  SessionStatus,
} from "@/types/research";
import type { UsageSummary } from "@/types/usage";

export async function fetchSessions(
  status?: SessionStatus,
  page = 1,
  size = 10,
): Promise<PaginatedResearchSessions> {
  const params: Record<string, string> = {
    page: String(page),
    size: String(size),
  };
  if (status) params.status = status;
  const { data } = await apiClient.get<PaginatedResearchSessions>(
    "/research/sessions",
    { params },
  );
  return data;
}

export async function fetchSessionDetail(
  sessionId: string,
): Promise<ResearchSessionDetail> {
  const { data } = await apiClient.get<ResearchSessionDetail>(
    `/research/sessions/${sessionId}`,
  );
  return data;
}

export function sessionEventsUrl(sessionId: string): string {
  return `${apiClient.defaults.baseURL}/research/sessions/${sessionId}/events`;
}

export async function fetchOutline(sessionId: string): Promise<OutlineResponse> {
  const { data } = await apiClient.get<OutlineResponse>(
    `/research/sessions/${sessionId}/outline`,
  );
  return data;
}

export async function updateOutline(
  sessionId: string,
  outline: ArticleOutline,
): Promise<OutlineResponse> {
  const { data } = await apiClient.put<OutlineResponse>(
    `/research/sessions/${sessionId}/outline`,
    outline,
  );
  return data;
}

export async function regenerateOutline(
  sessionId: string,
  instruction?: string,
): Promise<OutlineResponse> {
  const { data } = await apiClient.post<OutlineResponse>(
    `/research/sessions/${sessionId}/outline/regenerate`,
    { instruction: instruction ?? null },
  );
  return data;
}

export async function approveOutline(sessionId: string): Promise<SessionActionResponse> {
  const { data } = await apiClient.post<SessionActionResponse>(
    `/research/sessions/${sessionId}/outline/approve`,
  );
  return data;
}

export async function cancelSession(sessionId: string): Promise<SessionActionResponse> {
  const { data } = await apiClient.post<SessionActionResponse>(
    `/research/sessions/${sessionId}/cancel`,
  );
  return data;
}

export async function fetchSessionArticle(
  sessionId: string,
): Promise<{ article_id: string } | null> {
  try {
    const { data } = await apiClient.get<{ article_id: string }>(
      `/research/sessions/${sessionId}/article`,
    );
    return data;
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.status === 404) return null;
    throw e;
  }
}

export async function fetchSessionUsage(
  sessionId: string,
): Promise<UsageSummary> {
  const { data } = await apiClient.get<UsageSummary>(
    `/research/sessions/${sessionId}/usage`,
  );
  return data;
}
