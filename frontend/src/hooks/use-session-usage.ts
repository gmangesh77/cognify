"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchArticleUsage } from "@/lib/api/articles";
import { fetchSessionUsage } from "@/lib/api/research";
import type { UsageSummary } from "@/types/usage";

const ACTIVE_REFETCH_MS = 10_000;

export function useSessionUsage(sessionId: string | null, isActive: boolean) {
  const query = useQuery<UsageSummary>({
    queryKey: ["session-usage", sessionId],
    queryFn: () => fetchSessionUsage(sessionId as string),
    enabled: sessionId !== null,
    refetchInterval: isActive ? ACTIVE_REFETCH_MS : false,
    staleTime: isActive ? 0 : 60_000,
  });
  return { usage: query.data ?? null };
}

export function useArticleUsage(articleId: string | null) {
  const query = useQuery<UsageSummary>({
    queryKey: ["article-usage", articleId],
    queryFn: () => fetchArticleUsage(articleId as string),
    enabled: articleId !== null,
    staleTime: 60_000,
  });
  return { usage: query.data ?? null };
}
