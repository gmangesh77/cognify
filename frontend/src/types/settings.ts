import type { SourceName } from "./sources";

export type SettingsTab =
  | "domains"
  | "llm"
  | "visuals"
  | "api-keys"
  | "seo"
  | "general";

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

export type ApiKeyService =
  | "anthropic"
  | "openai"
  | "google_ai"
  | "serpapi"
  | "ghost"
  | "newsapi"
  | "arxiv"
  | "reddit_client_id"
  | "reddit_client_secret"
  | "semantic_scholar"
  | "linkedin_access_token"
  | "linkedin_refresh_token";

export const API_KEY_SERVICES: { value: ApiKeyService; label: string }[] = [
  { value: "anthropic", label: "Anthropic API" },
  { value: "openai", label: "OpenAI" },
  { value: "google_ai", label: "Google AI (Gemini / Imagen)" },
  { value: "serpapi", label: "SerpAPI" },
  { value: "ghost", label: "Ghost Admin" },
  { value: "newsapi", label: "NewsAPI" },
  { value: "arxiv", label: "arXiv" },
  { value: "reddit_client_id", label: "Reddit Client ID" },
  { value: "reddit_client_secret", label: "Reddit Client Secret" },
  { value: "semantic_scholar", label: "Semantic Scholar" },
  { value: "linkedin_access_token", label: "LinkedIn Access Token" },
  { value: "linkedin_refresh_token", label: "LinkedIn Refresh Token" },
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

// Phase 2 visuals UX — provider/model selector for image generation.
// Provider keys must match backend `src/services/visuals/providers/*`.
export type ImageProvider =
  | "dalle_3"
  | "gemini_flash"
  | "gemini_3_pro"
  | "imagen_4";

export const IMAGE_PROVIDER_OPTIONS: ReadonlyArray<{
  value: ImageProvider;
  label: string;
  vendor: "openai" | "google";
  models: ReadonlyArray<{ value: string; label: string }>;
}> = [
  {
    value: "dalle_3",
    label: "OpenAI · DALL·E 3",
    vendor: "openai",
    models: [{ value: "dall-e-3", label: "dall-e-3 (default)" }],
  },
  {
    value: "gemini_flash",
    label: "Google · Gemini Flash",
    vendor: "google",
    models: [
      {
        value: "gemini-2.5-flash-image",
        label: "gemini-2.5-flash-image (default)",
      },
    ],
  },
  {
    value: "gemini_3_pro",
    label: "Google · Gemini 3 Pro (preview)",
    vendor: "google",
    models: [
      {
        value: "gemini-3-pro-image-preview",
        label: "gemini-3-pro-image-preview (default)",
      },
    ],
  },
  {
    value: "imagen_4",
    label: "Google · Imagen 4",
    vendor: "google",
    models: [
      { value: "imagen-4.0-generate-001", label: "imagen-4.0-generate-001 (default)" },
    ],
  },
];

export interface LlmConfig {
  primaryModel: PrimaryModel;
  draftingModel: DraftingModel;
  imageGeneration: ImageModel;
  imageProvider: ImageProvider;
  imageModel: string | null;
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

/**
 * Audience persona keys mirror `src/services/visuals/persona_directions.py`.
 * The full list is fetched at boot via `/visuals/styles`; this union is the
 * subset surfaced in the Settings UI and the Visual Studio panel.
 */
export type AudiencePersona =
  | "general_business"
  | "ceo"
  | "cto"
  | "marketer"
  | "hr"
  | "salesperson"
  | "finance"
  | "operations";

export interface GeneralConfig {
  articleLengthTarget: ArticleLength;
  contentTone: ContentTone;
  defaultAudiencePersona: AudiencePersona;
}
