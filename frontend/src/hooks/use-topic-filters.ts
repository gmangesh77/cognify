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

export function useTopicFilters(topics: RankedTopic[]) {
  const [filters, setFiltersState] = useState<TopicFilters>(DEFAULT_FILTERS);

  const setFilters = (update: Partial<TopicFilters>) => {
    setFiltersState((prev) => ({ ...prev, ...update }));
  };

  const filteredTopics = useMemo(() => {
    const now = Date.now();
    return topics.filter((t) => {
      if (filters.sources.length > 0 && !filters.sources.includes(t.source)) return false;
      if (filters.domain && t.domain !== filters.domain) return false;
      if (filters.timeRange !== "all") {
        const ms = TIME_RANGE_MS[filters.timeRange];
        if (ms && now - new Date(t.discovered_at).getTime() > ms) return false;
      }
      return true;
    });
  }, [topics, filters]);

  return { filteredTopics, filters, setFilters };
}
