import { useQuery } from "@tanstack/react-query";
import { fetchMetrics } from "@/lib/api/metrics";
import type { DashboardMetrics } from "@/types/api";

const EMPTY_METRICS: DashboardMetrics = {
  topics_discovered: { value: 0, trend: 0, direction: "up" },
  articles_generated: { value: 0, trend: 0, direction: "up" },
  avg_research_time: { value: "0m", trend: 0, direction: "up" },
  published: { value: 0, trend: 0, direction: "up" },
};

export function useMetrics() {
  return useQuery({
    queryKey: ["metrics"],
    queryFn: async () => {
      try {
        return await fetchMetrics();
      } catch {
        return EMPTY_METRICS;
      }
    },
    staleTime: 60 * 1000,
    refetchInterval: 60 * 1000,
  });
}
