import { useQuery } from "@tanstack/react-query";
import type {
  PaginatedResearchSessions,
  ResearchSessionDetail,
  SessionStatus,
} from "@/types/research";
import { getMockSessions, mockSessionDetails } from "@/lib/mock/research-sessions";

async function fetchSessions(
  status?: SessionStatus,
  page = 1,
  size = 10,
): Promise<PaginatedResearchSessions> {
  // TODO: Replace with GET /api/v1/research/sessions?status=...&page=...&size=...
  return getMockSessions(status, page, size);
}

async function fetchSessionDetail(
  sessionId: string,
): Promise<ResearchSessionDetail | undefined> {
  // TODO: Replace with GET /api/v1/research/sessions/{sessionId}
  return mockSessionDetails[sessionId];
}

export function useResearchSessions(
  status?: SessionStatus,
  page = 1,
  size = 10,
) {
  return useQuery({
    queryKey: ["research-sessions", status, page, size],
    queryFn: () => fetchSessions(status, page, size),
    staleTime: 15 * 60 * 1000,
  });
}

export function useResearchSession(sessionId: string | null) {
  return useQuery({
    queryKey: ["research-session", sessionId],
    queryFn: () => fetchSessionDetail(sessionId!),
    enabled: sessionId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "planning" || status === "in_progress") return 10_000;
      return false;
    },
  });
}
