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
