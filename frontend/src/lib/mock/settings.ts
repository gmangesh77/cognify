import type {
  DomainConfig,
  ApiKeyConfig,
  ApiKeyService,
  LlmConfig,
  SeoDefaults,
  GeneralConfig,
} from "@/types/settings";

export const API_KEY_SERVICES: { value: ApiKeyService; label: string }[] = [
  { value: "anthropic", label: "Anthropic API" },
  { value: "serpapi", label: "SerpAPI" },
  { value: "ghost", label: "Ghost Admin" },
  { value: "newsapi", label: "NewsAPI" },
  { value: "arxiv", label: "arXiv" },
];

export const mockDomains: DomainConfig[] = [
  {
    id: "dom-1",
    name: "Cybersecurity",
    status: "active",
    trendSources: ["google_trends", "reddit", "hackernews"],
    keywords: ["security", "threats", "CVE"],
    articleCount: 24,
  },
  {
    id: "dom-2",
    name: "AI & Machine Learning",
    status: "inactive",
    trendSources: ["arxiv", "hackernews", "reddit"],
    keywords: ["LLM", "Transformers", "GPT"],
    articleCount: 7,
  },
];

export const mockApiKeys: ApiKeyConfig[] = [
  { id: "key-1", service: "anthropic", maskedKey: "sk-ant-\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u20227f3a", status: "active" },
  { id: "key-2", service: "serpapi", maskedKey: "serp-\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u20222b1c", status: "active" },
  { id: "key-3", service: "ghost", maskedKey: "ghost-\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u20229d4e", status: "active" },
  { id: "key-4", service: "newsapi", maskedKey: "news-\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u20224a8f", status: "active" },
];

export const mockLlmConfig: LlmConfig = {
  primaryModel: "claude-opus-4",
  draftingModel: "claude-sonnet-4",
  imageGeneration: "stable-diffusion-xl",
};

export const mockSeoDefaults: SeoDefaults = {
  autoMetaTags: true,
  keywordOptimization: true,
  autoCoverImages: true,
  includeCitations: true,
  humanReviewBeforePublish: true,
};

export const mockGeneralConfig: GeneralConfig = {
  articleLengthTarget: "3000-5000",
  contentTone: "professional",
};
