import { apiClient } from "./client";
import type {
  Publication,
  PublicationListResponse,
  PlatformSummary,
} from "@/types/publishing";
import type { PublishResult } from "./articles";

export async function getPublications(params: {
  page?: number;
  size?: number;
  platform?: string;
  status?: string;
}): Promise<PublicationListResponse> {
  const { data } = await apiClient.get<PublicationListResponse>(
    "/publications",
    { params },
  );
  return data;
}

export async function getPublication(id: string): Promise<Publication> {
  const { data } = await apiClient.get<Publication>(`/publications/${id}`);
  return data;
}

export async function getPlatformSummaries(): Promise<PlatformSummary[]> {
  const { data } = await apiClient.get<PlatformSummary[]>(
    "/publications/summaries",
  );
  return data;
}

export async function retryPublication(id: string): Promise<PublishResult> {
  const { data } = await apiClient.post<PublishResult>(
    `/publications/${id}/retry`,
  );
  return data;
}
