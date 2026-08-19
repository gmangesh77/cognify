import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import {
  approveOutline,
  cancelSession,
  fetchOutline,
  regenerateOutline,
  updateOutline,
} from "@/lib/api/research";
import type { ArticleOutline, OutlineResponse } from "@/types/research";

function parseValidationErrors(error: unknown): string[] {
  if (!axios.isAxiosError(error) || error.response?.status !== 422) return [];
  const detail = error.response.data?.detail;
  if (Array.isArray(detail)) return detail.map(String);
  if (detail != null) return [String(detail)];
  return [];
}

/**
 * Loads the outline pending review for a session and exposes save /
 * regenerate / approve mutations. All three keep the query cache in sync
 * so the component always renders the latest server copy after a mutation.
 */
export function useOutlineReview(sessionId: string) {
  const queryClient = useQueryClient();
  const queryKey = ["session-outline", sessionId];

  const outlineQuery = useQuery({
    queryKey,
    queryFn: () => fetchOutline(sessionId),
  });

  const saveMutation = useMutation({
    mutationFn: (outline: ArticleOutline) => updateOutline(sessionId, outline),
    onSuccess: (data) => queryClient.setQueryData<OutlineResponse>(queryKey, data),
  });

  const regenerateMutation = useMutation({
    mutationFn: (instruction?: string) => regenerateOutline(sessionId, instruction),
    onSuccess: (data) => queryClient.setQueryData<OutlineResponse>(queryKey, data),
  });

  const approveMutation = useMutation({
    mutationFn: () => approveOutline(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["research-session", sessionId] });
    },
  });

  const validationErrors = [
    ...parseValidationErrors(saveMutation.error),
    ...parseValidationErrors(regenerateMutation.error),
  ];

  return {
    outline: outlineQuery.data,
    isLoading: outlineQuery.isLoading,
    save: saveMutation.mutateAsync,
    regenerate: regenerateMutation.mutateAsync,
    approve: approveMutation.mutateAsync,
    isSaving: saveMutation.isPending,
    isRegenerating: regenerateMutation.isPending,
    isApproving: approveMutation.isPending,
    validationErrors,
  };
}

/** Cancels an in-flight research/content pipeline. Kept separate from
 * useOutlineReview so it can be used from SessionProgress's header even
 * when the session is not currently awaiting outline review. */
export function useCancelSession(sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => cancelSession(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["research-session", sessionId] });
    },
  });
}
