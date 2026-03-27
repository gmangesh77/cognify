import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getPublications,
  getPlatformSummaries,
  retryPublication,
} from "@/lib/api/publications";

interface PublicationFilters {
  platform?: string;
  status?: string;
  page?: number;
}

export function usePublications(filters: PublicationFilters = {}) {
  return useQuery({
    queryKey: ["publications", filters],
    queryFn: () =>
      getPublications({
        page: filters.page ?? 1,
        size: 20,
        platform: filters.platform,
        status: filters.status,
      }),
    staleTime: 30 * 1000,
  });
}

export function usePlatformSummaries() {
  return useQuery({
    queryKey: ["platform-summaries"],
    queryFn: getPlatformSummaries,
    staleTime: 60 * 1000,
  });
}

export function useRetryPublication() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => retryPublication(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["publications"] });
      queryClient.invalidateQueries({ queryKey: ["platform-summaries"] });
    },
  });
}
