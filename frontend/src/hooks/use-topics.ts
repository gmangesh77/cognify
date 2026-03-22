import { useQuery } from "@tanstack/react-query";
import type { RankedTopic } from "@/types/api";
import { fetchPersistedTopics } from "@/lib/api/trends";
import type { PersistedTopic } from "@/lib/api/trends";

function toRankedTopic(t: PersistedTopic): RankedTopic {
  const hoursAgo =
    (Date.now() - new Date(t.discovered_at).getTime()) / 3_600_000;
  let trend_status: RankedTopic["trend_status"] = "steady";
  if (t.velocity >= 50 && (t.composite_score ?? 0) >= 80)
    trend_status = "trending";
  else if (t.velocity >= 30) trend_status = "rising";
  else if (hoursAgo <= 24) trend_status = "new";

  return {
    title: t.title,
    description: t.description,
    source: t.source,
    external_url: t.external_url,
    trend_score: t.trend_score,
    discovered_at: t.discovered_at,
    velocity: t.velocity,
    domain_keywords: [],
    composite_score: t.composite_score ?? t.trend_score,
    rank: t.rank ?? 0,
    source_count: t.source_count,
    domain: t.domain,
    trend_status,
  };
}

export function useTopics() {
  return useQuery({
    queryKey: ["topics"],
    queryFn: async () => {
      try {
        const result = await fetchPersistedTopics("", 1, 10);
        return result.items.map(toRankedTopic);
      } catch {
        return [] as RankedTopic[];
      }
    },
    staleTime: 5 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  });
}
