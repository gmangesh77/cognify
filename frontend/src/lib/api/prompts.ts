import { apiClient } from "@/lib/api/client";
import type { PromptView } from "@/types/prompts";

export async function listPrompts(): Promise<PromptView[]> {
  const { data } = await apiClient.get<{ items: PromptView[] }>("/prompts");
  return data.items;
}

export async function updatePrompt(key: string, template: string): Promise<PromptView> {
  const { data } = await apiClient.put<PromptView>(
    `/prompts/${encodeURIComponent(key)}`,
    { template },
  );
  return data;
}

export async function resetPrompt(key: string): Promise<PromptView> {
  const { data } = await apiClient.delete<PromptView>(
    `/prompts/${encodeURIComponent(key)}`,
  );
  return data;
}

interface AxiosLike {
  response?: { status?: number; data?: { detail?: { violations?: string[] } } };
}

export function extractPromptViolations(err: unknown): string[] {
  const e = err as AxiosLike;
  if (e?.response?.status !== 422) return [];
  return e.response.data?.detail?.violations ?? [];
}
