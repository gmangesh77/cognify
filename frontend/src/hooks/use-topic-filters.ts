import { useState, useMemo } from "react";
import type { RankedTopic, TopicFilters } from "@/types/api";

const TIME_RANGE_MS: Record<string, number> = {
  "1h": 3600000,
  "24h": 86400000,
  "7d": 604800000,
  "30d": 2592000000,
};

const DEFAULT_FILTERS: TopicFilters = {
  sources: [],
  timeRange: "all",
  domain: "",
};

function isWithinTimeRange(discoveredAt: string, timeRange: string): boolean {
  if (timeRange === "all") return true;
  const ms = TIME_RANGE_MS[timeRange];
  if (!ms) return true;
  const age = Date.now() - new Date(discoveredAt).getTime();
  return age <= ms;
}

export function useTopicFilters(
  topics: RankedTopic[],
  initialFilters: Partial<TopicFilters> = {},
) {
  const [filters, setFiltersState] = useState<TopicFilters>({
    ...DEFAULT_FILTERS,
    ...initialFilters,
  });

  const setFilters = (update: Partial<TopicFilters>) => {
    setFiltersState((prev) => ({ ...prev, ...update }));
  };

  const filteredTopics = useMemo(() => {
    return topics.filter((t) => {
      if (filters.sources.length > 0 && !filters.sources.includes(t.source)) return false;
      if (filters.domain && t.domain !== filters.domain) return false;
      if (!isWithinTimeRange(t.discovered_at, filters.timeRange)) return false;
      return true;
    });
  }, [topics, filters]);

  return { filteredTopics, filters, setFilters };
}
