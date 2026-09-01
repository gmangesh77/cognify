export type Role = "admin" | "editor" | "viewer";

const TOKEN_KEY = "cognify_access_token";

/** Role claim of the stored access token (client-side hint only — the API enforces RBAC). */
export function currentRole(): Role | null {
  if (typeof window === "undefined") return null;
  const token = localStorage.getItem(TOKEN_KEY);
  const payload = token?.split(".")[1];
  if (!payload) return null;
  try {
    const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    const role = (JSON.parse(json) as { role?: string }).role;
    return role === "admin" || role === "editor" || role === "viewer" ? role : null;
  } catch {
    return null;
  }
}
