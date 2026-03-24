import { apiClient } from "./client";

// ---- Domains ----

export async function fetchDomains() {
  const { data } = await apiClient.get("/settings/domains");
  return data.items;  // DomainConfig[]
}

export async function createDomain(body: {
  name: string;
  status: string;
  trend_sources: string[];
  keywords: string[];
}) {
  const { data } = await apiClient.post("/settings/domains", body);
  return data;
}

export async function updateDomain(id: string, body: Record<string, unknown>) {
  const { data } = await apiClient.put(`/settings/domains/${id}`, body);
  return data;
}

export async function deleteDomain(id: string) {
  await apiClient.delete(`/settings/domains/${id}`);
}

// ---- API Keys ----

export async function fetchApiKeys() {
  const { data } = await apiClient.get("/settings/api-keys");
  return data.items;
}

export async function addApiKey(body: { service: string; key: string }) {
  const { data } = await apiClient.post("/settings/api-keys", body);
  return data;
}

export async function rotateApiKey(id: string, body: { key: string }) {
  const { data } = await apiClient.put(`/settings/api-keys/${id}/rotate`, body);
  return data;
}

export async function deleteApiKey(id: string) {
  await apiClient.delete(`/settings/api-keys/${id}`);
}

// ---- LLM Config ----

export async function fetchLlmConfig() {
  const { data } = await apiClient.get("/settings/llm");
  return data;
}

export async function updateLlmConfig(body: Record<string, unknown>) {
  const { data } = await apiClient.put("/settings/llm", body);
  return data;
}

// ---- SEO Defaults ----

export async function fetchSeoDefaults() {
  const { data } = await apiClient.get("/settings/seo");
  return data;
}

export async function updateSeoDefaults(body: Record<string, unknown>) {
  const { data } = await apiClient.put("/settings/seo", body);
  return data;
}

// ---- General Config ----

export async function fetchGeneralConfig() {
  const { data } = await apiClient.get("/settings/general");
  return data;
}

export async function updateGeneralConfig(body: Record<string, unknown>) {
  const { data } = await apiClient.put("/settings/general", body);
  return data;
}
