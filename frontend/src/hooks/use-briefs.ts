import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createBrief, deleteBrief, duplicateBrief, fetchBriefs, updateBrief } from "@/lib/api/briefs";
import type { Brief, BriefCreate, BriefUpdate } from "@/types/brief";

export const BRIEFS_QUERY_KEY = ["briefs"] as const;

export function useBriefs() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: BRIEFS_QUERY_KEY, queryFn: fetchBriefs });
  const invalidate = () => qc.invalidateQueries({ queryKey: BRIEFS_QUERY_KEY });

  const createM = useMutation({ mutationFn: createBrief, onSuccess: invalidate });
  const updateM = useMutation({
    mutationFn: ({ id, body }: { id: string; body: BriefUpdate }) => updateBrief(id, body),
    onSuccess: invalidate,
  });
  const removeM = useMutation({ mutationFn: deleteBrief, onSuccess: invalidate });
  const duplicateM = useMutation({ mutationFn: duplicateBrief, onSuccess: invalidate });

  return {
    briefs: query.data ?? ([] as Brief[]),
    isLoading: query.isLoading,
    error: query.error ? (query.error as Error).message : null,
    create: (b: BriefCreate) => createM.mutateAsync(b),
    update: (id: string, body: BriefUpdate) => updateM.mutateAsync({ id, body }),
    remove: (id: string) => removeM.mutateAsync(id),
    duplicate: (id: string) => duplicateM.mutateAsync(id),
  };
}
