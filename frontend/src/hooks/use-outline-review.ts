import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useState } from "react";
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

/** Maps a failed mutation's error to a user-facing message, or `null` when
 * it's a 422 (those are surfaced separately via `validationErrors`) or not
 * an Axios error at all. Shared by every outline-review and cancel mutation
 * so the same status codes always read the same way. */
function friendlyMutationError(error: unknown): string | null {
  if (!axios.isAxiosError(error)) return null;
  const status = error.response?.status;
  if (status === 422) return null;
  const detail = error.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (status === 409) return "Session is no longer awaiting review";
  if (status === 429) return "Too many regenerate requests — try again in a minute";
  return `Action failed (HTTP ${status ?? "unknown"})`;
}

/**
 * Loads the outline pending review for a session and exposes save /
 * regenerate / approve mutations. All three keep the query cache in sync
 * so the component always renders the latest server copy after a mutation.
 */
export function useOutlineReview(sessionId: string) {
  const queryClient = useQueryClient();
  const queryKey = ["session-outline", sessionId];
  const [actionError, setActionError] = useState<string | null>(null);

  const outlineQuery = useQuery({
    queryKey,
    queryFn: () => fetchOutline(sessionId),
  });

  const onActionError = (error: unknown) => {
    const message = friendlyMutationError(error);
    if (message) setActionError(message);
  };

  const saveMutation = useMutation({
    mutationFn: (outline: ArticleOutline) => updateOutline(sessionId, outline),
    onSuccess: (data) => {
      queryClient.setQueryData<OutlineResponse>(queryKey, data);
      setActionError(null);
    },
    onError: onActionError,
  });

  const regenerateMutation = useMutation({
    mutationFn: (instruction?: string) => regenerateOutline(sessionId, instruction),
    onSuccess: (data) => {
      queryClient.setQueryData<OutlineResponse>(queryKey, data);
      setActionError(null);
    },
    onError: onActionError,
  });

  const approveMutation = useMutation({
    mutationFn: () => approveOutline(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["research-session", sessionId] });
      setActionError(null);
    },
    onError: onActionError,
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
    actionError,
  };
}

/** Cancels an in-flight research/content pipeline. Kept separate from
 * useOutlineReview so it can be used from SessionProgress's header even
 * when the session is not currently awaiting outline review. */
export function useCancelSession(sessionId: string) {
  const queryClient = useQueryClient();
  const [cancelError, setCancelError] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: () => cancelSession(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["research-session", sessionId] });
      setCancelError(null);
    },
    onError: (error: unknown) => {
      const message = friendlyMutationError(error);
      if (message) setCancelError(message);
    },
  });
  return { ...mutation, cancelError };
}
