import { useQuery } from "@tanstack/react-query";
import { fetchMetrics } from "@/lib/api/metrics";
import { mockMetrics } from "@/lib/mock/metrics";

export function useMetrics() {
  return useQuery({
    queryKey: ["metrics"],
    queryFn: async () => {
      try {
        return await fetchMetrics();
      } catch {
        return mockMetrics;
      }
    },
    staleTime: 60 * 1000,
    refetchInterval: 60 * 1000,
  });
}
