"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchSessions } from "@/lib/api/research";
import { RESUMABLE_SESSION_FILTERS } from "@/lib/research/session-status";
import type { ResearchSessionSummary, SessionStatus } from "@/types/research";

/** Sessions worth a "Resume" link on the articles list (AUTHOR-007).
 *
 * Resumable sessions have NO canonical_articles row yet, so they can't
 * come from GET /articles — this is a separate query per backend filter
 * value ("failed" is a server-side group covering article_failed too).
 */
export function useResumableSessions() {
  const query = useQuery<ResearchSessionSummary[]>({
    queryKey: ["resumable-sessions"],
    queryFn: async () => {
      try {
        const pages = await Promise.all(
          RESUMABLE_SESSION_FILTERS.map((status) =>
            fetchSessions(status as SessionStatus, 1, 10),
          ),
        );
        const seen = new Map<string, ResearchSessionSummary>();
        for (const page of pages) {
          for (const item of page.items) seen.set(item.session_id, item);
        }
        return [...seen.values()];
      } catch {
        return [];
      }
    },
    staleTime: 30_000,
  });
  return { sessions: query.data ?? [] };
}
