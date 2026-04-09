import { useQuery } from "@tanstack/react-query";
import { fetchMetrics, fetchKnowledgeBaseStats } from "@/lib/api/metrics";

export function useMetrics() {
  return useQuery({
    queryKey: ["metrics"],
    queryFn: fetchMetrics,
    staleTime: 60 * 1000,
    refetchInterval: 60 * 1000,
  });
}

export function useKnowledgeBaseStats() {
  return useQuery({
    queryKey: ["knowledge-base-stats"],
    queryFn: fetchKnowledgeBaseStats,
    staleTime: 60 * 1000,
  });
}
