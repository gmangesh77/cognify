import { apiClient } from "@/lib/api/client";
import type {
  PersonaCreate,
  PersonaDetail,
  PersonaSummary,
  PersonaUpdate,
  VoiceScore,
} from "@/types/persona";

export async function listPersonas(): Promise<PersonaSummary[]> {
  const { data } = await apiClient.get<{ items: PersonaSummary[] }>("/personas");
  return data.items;
}

export async function createPersona(body: PersonaCreate): Promise<PersonaSummary> {
  const { data } = await apiClient.post<PersonaSummary>("/personas", body);
  return data;
}

export async function getPersona(id: string): Promise<PersonaDetail> {
  const { data } = await apiClient.get<PersonaDetail>(`/personas/${id}`);
  return data;
}

export async function updatePersona(id: string, patch: PersonaUpdate): Promise<PersonaSummary> {
  const { data } = await apiClient.patch<PersonaSummary>(`/personas/${id}`, patch);
  return data;
}

export async function deletePersona(id: string): Promise<void> {
  await apiClient.delete(`/personas/${id}`);
}

export async function addSample(id: string, text: string): Promise<PersonaDetail> {
  const { data } = await apiClient.post<PersonaDetail>(`/personas/${id}/samples`, { text });
  return data;
}

export async function deleteSample(id: string, sampleId: string): Promise<PersonaDetail> {
  const { data } = await apiClient.delete<PersonaDetail>(`/personas/${id}/samples/${sampleId}`);
  return data;
}

export async function scorePersona(id: string, text: string): Promise<VoiceScore> {
  const { data } = await apiClient.post<VoiceScore>(`/personas/${id}/score`, { text });
  return data;
}

interface AxiosLike {
  response?: { status?: number; data?: { detail?: { violations?: string[] } } };
}

export function extractPersonaViolations(err: unknown): string[] {
  const e = err as AxiosLike;
  if (e?.response?.status !== 422) return [];
  return e.response.data?.detail?.violations ?? [];
}
