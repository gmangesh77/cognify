import { apiClient, setAccessToken } from "./client";
import type { LoginRequest, TokenResponse } from "@/types/api";

export async function login(credentials: LoginRequest): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>("/auth/login", credentials);
  setAccessToken(data.access_token);
  return data;
}

export async function logout(): Promise<void> {
  try {
    await apiClient.post("/auth/logout");
  } finally {
    setAccessToken(null);
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  }
}
