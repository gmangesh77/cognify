import { useQuery } from "@tanstack/react-query";
import type {
  ResearchSessionDetail,
  SessionStatus,
} from "@/types/research";
import { fetchSessions, fetchSessionDetail } from "@/lib/api/research";

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
      const status = (query.state.data as ResearchSessionDetail | undefined)
        ?.status;
      if (status === "planning" || status === "in_progress") return 10_000;
      return false;
    },
  });
}
