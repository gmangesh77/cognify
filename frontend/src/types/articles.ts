export type ArticleStatus = "draft" | "complete" | "published";

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

export interface ImageAsset {
  id: string;
  url: string;
  caption: string | null;
  altText: string | null;
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
