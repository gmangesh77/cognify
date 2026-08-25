// AUTHOR-007 — real editorial states ("complete" removed; the badge keeps
// a legacy alias for the dashboard's separate Article union in types/api.ts).
export type ArticleStatus = "draft" | "in_review" | "approved" | "published";

export interface ArticleListItem {
  id: string;
  title: string;
  summary: string;
  domain: string;
  status: ArticleStatus;
  wordCount: number;
  generatedAt: string;
}

export interface Citation {
  index: number;
  title: string;
  url: string;
  authors: string[];
  publishedAt: string | null;
}

export interface Provenance {
  researchSessionId: string;
  primaryModel: string;
  draftingModel: string;
  embeddingModel: string;
  embeddingVersion: string;
}

export interface StructuredDataLD {
  headline: string;
  description: string;
  keywords: string[];
  datePublished: string;
  dateModified: string;
}

export interface SEOMetadata {
  title: string;
  description: string;
  keywords: string[];
  canonicalUrl: string | null;
  structuredData: StructuredDataLD | null;
}

export interface ImageAssetMetadata {
  diagram_type?: string;
  source_section?: number;
  mermaid_syntax?: string;
  // Image-planner (Epic 10) fields. The planner stamps `section_index`
  // (not the legacy `source_section`), plus the placement anchor and the
  // role_style used to decide cover vs inline rendering.
  section_index?: number;
  placement_anchor?: string;
  role_style?: string;
}

export interface ImageAsset {
  id: string;
  url: string;
  caption: string | null;
  altText: string | null;
  metadata?: ImageAssetMetadata | null;
}

export interface WorkflowStep {
  name: string;
  durationSeconds: number;
}

export interface ArticleDetail {
  id: string;
  title: string;
  subtitle: string | null;
  bodyMarkdown: string;
  summary: string;
  keyClaims: string[];
  contentType: string;
  seo: SEOMetadata;
  citations: Citation[];
  visuals: ImageAsset[];
  authors: string[];
  domain: string;
  generatedAt: string;
  provenance: Provenance;
  aiGenerated: boolean;
  status: ArticleStatus;
  wordCount: number;
  workflow: WorkflowStep[];
}

// AUTHOR-006 — metadata editing wire types
export interface ArticleMetadataPatch {
  title?: string;
  subtitle?: string;
  seo_title?: string;
  seo_description?: string;
  keywords?: string[];
  status?: ArticleStatus; // AUTHOR-007
}

export interface FieldWarning {
  field: string;
  message: string;
}

export interface ArticleMetadataResult {
  id: string;
  title: string;
  subtitle: string | null;
  seo: { title: string; description: string; keywords: string[] };
  warnings: FieldWarning[];
}

export type SeoRegenerateField = "seo_title" | "seo_description" | "keywords";

export interface SeoRegenerateResult {
  field: string;
  value: string | string[];
  warnings: FieldWarning[];
}
