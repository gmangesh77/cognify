import { useCallback } from "react";
import type { ShowToast } from "@/components/ui/toaster";
import { attachVisualToArticle, publishArticle } from "@/lib/api/articles";
import type { ImageSpec, RenderResponse } from "@/types/visuals";

export interface ArticleActionsDeps {
  id: string;
  refetch: () => Promise<unknown>;
  showToast: ShowToast;
}

export type InsertableVisual = { spec: ImageSpec; render: RenderResponse };

async function attachOne(id: string, v: InsertableVisual): Promise<boolean> {
  const url = v.render.image_url;
  // Only hosted URLs (MinIO/CDN) can be persisted. Base64 fallback
  // cannot be re-served from the article endpoint without first
  // uploading to object storage — count it as failed instead of
  // writing an unusable data: URL to the DB.
  if (!url) return false;
  try {
    await attachVisualToArticle(id, {
      url,
      alt_text: v.spec.alt_text,
      caption: v.spec.rationale ?? null,
      metadata: {
        spec_id: v.spec.id,
        provider: v.render.provider,
        model: v.render.model,
        section_index: v.spec.placement.section_index,
        role_style: v.spec.role_style,
      },
    });
    return true;
  } catch {
    return false;
  }
}

async function publishOne(id: string, platform: string): Promise<string> {
  try {
    const res = await publishArticle(id, platform);
    if (res.status === "success") {
      return `${platform}: published${res.external_url ? ` (${res.external_url})` : ""}`;
    }
    return `${platform}: ${res.error_message ?? "failed"}`;
  } catch {
    return `${platform}: request failed`;
  }
}

/** Side-effecting article actions lifted out of the detail page (AUTHOR-004 split). */
export function useArticleActions({ id, refetch, showToast }: ArticleActionsDeps) {
  const insertVisuals = useCallback(
    async (visuals: InsertableVisual[]) => {
      let attached = 0;
      for (const v of visuals) {
        if (await attachOne(id, v)) attached += 1;
      }
      const failed = visuals.length - attached;
      await refetch();
      const parts: string[] = [];
      if (attached > 0) parts.push(`${attached} inserted`);
      if (failed > 0) parts.push(`${failed} failed (no hosted URL)`);
      showToast(parts.join(" · ") || "Nothing to insert", 6000);
    },
    [id, refetch, showToast],
  );

  const publish = useCallback(
    async (platforms: string[]) => {
      const results: string[] = [];
      for (const platform of platforms) {
        results.push(await publishOne(id, platform));
      }
      // A successful publish flips the article to "published" server-side
      // (AUTHOR-007) — refetch so the header badge/transition update.
      await refetch();
      showToast(results.join(" | "), 8000);
    },
    [id, refetch, showToast],
  );

  return { insertVisuals, publish };
}
