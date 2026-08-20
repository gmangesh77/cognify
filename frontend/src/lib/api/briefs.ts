import { apiClient } from "@/lib/api/client";
import type { Brief, BriefCreate, BriefUpdate } from "@/types/brief";

export async function fetchBriefs(): Promise<Brief[]> {
  const { data } = await apiClient.get<Brief[]>("/briefs");
  return data;
}

export async function createBrief(body: BriefCreate): Promise<Brief> {
  const { data } = await apiClient.post<Brief>("/briefs", body);
  return data;
}

export async function updateBrief(id: string, body: BriefUpdate): Promise<Brief> {
  const { data } = await apiClient.patch<Brief>(`/briefs/${id}`, body);
  return data;
}

export async function deleteBrief(id: string): Promise<void> {
  await apiClient.delete(`/briefs/${id}`);
}

export async function duplicateBrief(id: string): Promise<Brief> {
  const { data } = await apiClient.post<Brief>(`/briefs/${id}/duplicate`);
  return data;
}
