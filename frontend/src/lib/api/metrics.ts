import { apiClient } from "./client";
import type { DashboardMetrics } from "@/types/api";

export interface KnowledgeBaseStats {
  total_sessions: number;
  total_sources: number;
  total_embeddings: number;
}

export async function fetchMetrics(): Promise<DashboardMetrics> {
  const { data } = await apiClient.get<DashboardMetrics>("/metrics");
  return data;
}

export async function fetchKnowledgeBaseStats(): Promise<KnowledgeBaseStats> {
  const { data } = await apiClient.get<KnowledgeBaseStats>(
    "/metrics/knowledge-base",
  );
  return data;
}
