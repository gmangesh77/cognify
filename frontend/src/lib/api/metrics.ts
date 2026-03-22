import { apiClient } from "./client";
import type { DashboardMetrics } from "@/types/api";

export async function fetchMetrics(): Promise<DashboardMetrics> {
  const { data } = await apiClient.get<DashboardMetrics>("/metrics");
  return data;
}
