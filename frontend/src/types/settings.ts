import type { SourceName } from "./sources";

export type SettingsTab = "domains" | "llm" | "api-keys" | "seo" | "general";

// --- Domain ---

export interface DomainConfig {
  id: string;
  name: string;
  status: "active" | "inactive";
  trendSources: SourceName[];
  keywords: string[];
  articleCount: number;
}

// --- API Keys ---

export type ApiKeyService = "anthropic" | "serpapi" | "ghost" | "newsapi" | "arxiv";

export const API_KEY_SERVICES: { value: ApiKeyService; label: string }[] = [
  { value: "anthropic", label: "Anthropic API" },
  { value: "serpapi", label: "SerpAPI" },
  { value: "ghost", label: "Ghost Admin" },
  { value: "newsapi", label: "NewsAPI" },
  { value: "arxiv", label: "arXiv" },
];

export interface ApiKeyConfig {
  id: string;
  service: ApiKeyService;
  maskedKey: string;
  status: "active" | "inactive";
}

// --- LLM ---

export type PrimaryModel = "claude-opus-4" | "claude-sonnet-4" | "gpt-4o";
export type DraftingModel = "claude-sonnet-4" | "claude-opus-4" | "gpt-4o-mini";
export type ImageModel = "stable-diffusion-xl" | "dall-e-3" | "midjourney";

export interface LlmConfig {
  primaryModel: PrimaryModel;
  draftingModel: DraftingModel;
  imageGeneration: ImageModel;
}

// --- SEO ---

export interface SeoDefaults {
  autoMetaTags: boolean;
  keywordOptimization: boolean;
  autoCoverImages: boolean;
  includeCitations: boolean;
  humanReviewBeforePublish: boolean;
}

// --- General ---

export type ArticleLength = "1000-2000" | "3000-5000" | "5000-8000";
export type ContentTone = "professional" | "casual" | "technical" | "educational";

export interface GeneralConfig {
  articleLengthTarget: ArticleLength;
  contentTone: ContentTone;
}
