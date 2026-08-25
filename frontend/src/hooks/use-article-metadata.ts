"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { patchArticleMetadata, regenerateSeoField } from "@/lib/api/articles";
import type {
  ArticleMetadataPatch,
  ArticleMetadataResult,
  SeoRegenerateField,
  SeoRegenerateResult,
} from "@/types/articles";

export function useArticleMetadata(articleId: string) {
  const queryClient = useQueryClient();

  const saveMutation = useMutation({
    mutationFn: (patch: ArticleMetadataPatch) =>
      patchArticleMetadata(articleId, patch),
    onSuccess: () => {
      // Explicit invalidate bypasses use-article's 5-minute staleTime so
      // the header re-renders from fresh data (review §6 #7 stale view).
      void queryClient.invalidateQueries({ queryKey: ["article", articleId] });
      // Status changes also affect the list badges/filters and the
      // dashboard recent-articles rows (AUTHOR-007).
      void queryClient.invalidateQueries({ queryKey: ["article-list"] });
      void queryClient.invalidateQueries({ queryKey: ["articles"] });
    },
  });

  const regenerateMutation = useMutation({
    mutationFn: (field: SeoRegenerateField) =>
      regenerateSeoField(articleId, field),
  });

  return {
    save: (patch: ArticleMetadataPatch): Promise<ArticleMetadataResult> =>
      saveMutation.mutateAsync(patch),
    saving: saveMutation.isPending,
    regenerate: (field: SeoRegenerateField): Promise<SeoRegenerateResult> =>
      regenerateMutation.mutateAsync(field),
    regenerating: regenerateMutation.isPending,
  };
}
