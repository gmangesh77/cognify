import { useQuery } from "@tanstack/react-query";
import type {
  ResearchSessionDetail,
  SessionStatus,
} from "@/types/research";
import { fetchSessions, fetchSessionDetail } from "@/lib/api/research";

/** Statuses that still poll the session detail endpoint for updates. */
export const ACTIVE_POLL_STATUSES: readonly string[] = [
  "planning",
  "in_progress",
  "researching",
  "evaluating",
  "running",
  "complete",
  "awaiting_outline_review",
  "generating_article",
];

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
      if (status && ACTIVE_POLL_STATUSES.includes(status)) return 5_000;
      return false;
    },
  });
}
