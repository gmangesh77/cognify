import type { DashboardMetrics } from "@/types/api";

export const mockMetrics: DashboardMetrics = {
  topics_discovered: { value: 147, trend: 12, direction: "up" },
  articles_generated: { value: 38, trend: 18, direction: "up" },
  avg_research_time: { value: "4.2m", trend: 15, direction: "down" },
  published: { value: 24, trend: 8, direction: "up" },
};
