import { useQuery } from "@tanstack/react-query";
import { fetchArticle } from "@/lib/api/articles";
import type { ArticleDetail } from "@/types/articles";
import type { ArticleResponse } from "@/lib/api/articles";

function toDetail(a: ArticleResponse): ArticleDetail {
  return {
    id: a.id,
    title: a.title,
    subtitle: a.subtitle ?? "",
    bodyMarkdown: a.body_markdown,
    summary: a.summary,
    keyClaims: a.key_claims,
    contentType: a.content_type,
    seo: {
      title: a.seo.title,
      description: a.seo.description,
      keywords: a.seo.keywords,
      canonicalUrl: a.seo.canonical_url ?? null,
      structuredData: a.seo.structured_data
        ? {
            headline: a.seo.structured_data.headline,
            description: a.seo.structured_data.description,
            keywords: a.seo.structured_data.keywords,
            datePublished: a.seo.structured_data.date_published,
            dateModified: a.seo.structured_data.date_modified,
          }
        : null,
    },
    citations: a.citations.map((c) => ({
      index: c.index,
      title: c.title,
      url: c.url,
      authors: c.authors,
      publishedAt: c.published_at,
    })),
    visuals: a.visuals.map((v) => ({
      id: v.id,
      url: v.url,
      caption: v.caption,
      altText: v.alt_text,
    })),
    authors: a.authors,
    domain: a.domain,
    generatedAt: a.generated_at,
    provenance: {
      researchSessionId: a.provenance.research_session_id,
      primaryModel: a.provenance.primary_model,
      draftingModel: a.provenance.drafting_model,
      embeddingModel: a.provenance.embedding_model,
      embeddingVersion: a.provenance.embedding_version,
    },
    aiGenerated: a.ai_generated,
    status: "complete",
    wordCount: a.body_markdown.split(/\s+/).length,
    workflow: [],
  };
}

export function useArticle(id: string) {
  const query = useQuery({
    queryKey: ["article", id],
    queryFn: async () => {
      try {
        const result = await fetchArticle(id);
        return { article: toDetail(result) };
      } catch {
        return { article: null };
      }
    },
    staleTime: 5 * 60 * 1000,
  });
  return { article: query.data?.article ?? null };
}
