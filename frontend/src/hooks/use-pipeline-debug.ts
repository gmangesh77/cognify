import { useQuery } from "@tanstack/react-query";
import { fetchDebugSessions, fetchPipelineDebug } from "@/lib/api/pipeline-debug";

export function useDebugSessions(page = 1, size = 20) {
  return useQuery({
    queryKey: ["debug-sessions", page, size],
    queryFn: () => fetchDebugSessions(page, size),
    staleTime: 30 * 1000,
  });
}

export function usePipelineDebug(sessionId: string | null) {
  return useQuery({
    queryKey: ["pipeline-debug", sessionId],
    queryFn: () => fetchPipelineDebug(sessionId!),
    enabled: sessionId !== null,
    staleTime: 15 * 1000,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      const active = [
        "planning", "in_progress", "researching", "evaluating",
        "running", "generating_article",
      ];
      if (status && active.includes(status)) return 5_000;
      return false;
    },
  });
}
