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
      const active = [
        "planning", "in_progress", "researching", "evaluating",
        "running", "complete", "generating_article",
      ];
      if (status && active.includes(status)) return 5_000;
      return false;
    },
  });
}
