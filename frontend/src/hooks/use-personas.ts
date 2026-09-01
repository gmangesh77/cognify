import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addSample,
  createPersona,
  deletePersona,
  deleteSample,
  getPersona,
  listPersonas,
  updatePersona,
} from "@/lib/api/personas";
import type { PersonaCreate, PersonaDetail, PersonaSummary, PersonaUpdate } from "@/types/persona";

export const PERSONAS_QUERY_KEY = ["personas"] as const;

export function usePersonas() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: PERSONAS_QUERY_KEY, queryFn: listPersonas });
  const invalidate = () => qc.invalidateQueries({ queryKey: PERSONAS_QUERY_KEY });

  const createM = useMutation({
    mutationFn: (body: PersonaCreate) => createPersona(body),
    onSuccess: invalidate,
  });
  const updateM = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: PersonaUpdate }) => updatePersona(id, patch),
    onSuccess: invalidate,
  });
  const removeM = useMutation({
    mutationFn: (id: string) => deletePersona(id),
    onSuccess: invalidate,
  });

  return {
    personas: query.data ?? ([] as PersonaSummary[]),
    isLoading: query.isLoading,
    error: query.error
      ? query.error instanceof Error
        ? query.error.message
        : "Failed to load personas"
      : null,
    create: (body: PersonaCreate) => createM.mutateAsync(body),
    update: (id: string, patch: PersonaUpdate) => updateM.mutateAsync({ id, patch }),
    remove: (id: string) => removeM.mutateAsync(id),
  };
}

export function usePersona(id: string | null) {
  const qc = useQueryClient();
  const detailKey = [...PERSONAS_QUERY_KEY, id] as const;
  const query = useQuery({
    queryKey: detailKey,
    queryFn: () => getPersona(id as string),
    enabled: id !== null,
  });
  // Invalidating the ["personas"] prefix also matches ["personas", id] —
  // one call refreshes both the list badges and this detail query.
  const invalidate = () => qc.invalidateQueries({ queryKey: PERSONAS_QUERY_KEY });

  const addSampleM = useMutation({
    mutationFn: (text: string) => addSample(id as string, text),
    onSuccess: invalidate,
  });
  const removeSampleM = useMutation({
    mutationFn: (sampleId: string) => deleteSample(id as string, sampleId),
    onSuccess: invalidate,
  });

  return {
    persona: (query.data ?? null) as PersonaDetail | null,
    isLoading: query.isLoading,
    addSample: (text: string) => addSampleM.mutateAsync(text),
    removeSample: (sampleId: string) => removeSampleM.mutateAsync(sampleId),
    isMutating: addSampleM.isPending || removeSampleM.isPending,
  };
}
