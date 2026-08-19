import axios from "axios";
import { apiClient } from "@/lib/api/client";
import type {
  PaginatedResearchSessions,
  ResearchSessionDetail,
  SessionStatus,
} from "@/types/research";

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
