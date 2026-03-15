import { useQuery } from "@tanstack/react-query";
import type { DashboardMetrics } from "@/types/api";
import { mockMetrics } from "@/lib/mock/metrics";

async function fetchMetrics(): Promise<DashboardMetrics> {
  // TODO: Replace with real API call when endpoint exists
  return mockMetrics;
}

export function useMetrics() {
  return useQuery({
    queryKey: ["metrics"],
    queryFn: fetchMetrics,
    staleTime: 15 * 60 * 1000,
  });
}
