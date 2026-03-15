import { useQuery } from "@tanstack/react-query";
import type { RankedTopic } from "@/types/api";
import { mockTopics } from "@/lib/mock/topics";

async function fetchTopics(): Promise<RankedTopic[]> {
  // TODO: Replace with GET /api/v1/dashboard/topics when endpoint exists
  return mockTopics;
}

export function useTopics() {
  return useQuery({
    queryKey: ["topics"],
    queryFn: fetchTopics,
    staleTime: 15 * 60 * 1000,
    refetchInterval: 15 * 60 * 1000,
  });
}
