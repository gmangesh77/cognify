import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { listPrompts, resetPrompt, updatePrompt } from "@/lib/api/prompts";
import type { PromptView } from "@/types/prompts";

export const PROMPTS_QUERY_KEY = ["prompts"] as const;

export function usePrompts() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: PROMPTS_QUERY_KEY, queryFn: listPrompts });
  const invalidate = () => qc.invalidateQueries({ queryKey: PROMPTS_QUERY_KEY });

  const saveM = useMutation({
    mutationFn: ({ key, template }: { key: string; template: string }) => updatePrompt(key, template),
    onSuccess: invalidate,
  });
  const resetM = useMutation({
    mutationFn: (key: string) => resetPrompt(key),
    onSuccess: invalidate,
  });

  return {
    prompts: query.data ?? ([] as PromptView[]),
    isLoading: query.isLoading,
    error: query.error ? (query.error instanceof Error ? query.error.message : "Failed to load prompts") : null,
    save: (key: string, template: string) => saveM.mutateAsync({ key, template }),
    reset: (key: string) => resetM.mutateAsync(key),
    isSaving: saveM.isPending || resetM.isPending,
  };
}
