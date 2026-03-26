import { useState, useCallback, useEffect } from "react";
import type {
  DomainConfig,
  LlmConfig,
  ApiKeyConfig,
  ApiKeyService,
  SeoDefaults,
  GeneralConfig,
  ArticleLength,
  ContentTone,
  PrimaryModel,
  DraftingModel,
  ImageModel,
} from "@/types/settings";
import type { SourceName } from "@/types/sources";
import * as settingsApi from "@/lib/api/settings";

// ---- Snake-case API shapes ----

interface ApiDomain {
  id: string;
  name: string;
  status: "active" | "inactive";
  trend_sources: string[];
  keywords: string[];
  article_count: number;
}

interface ApiApiKey {
  id: string;
  service: ApiKeyService;
  masked_key: string;
  status: "active" | "inactive";
}

interface ApiLlmConfig {
  primary_model: string;
  drafting_model: string;
  image_generation: string;
}

interface ApiSeoDefaults {
  auto_meta_tags: boolean;
  keyword_optimization: boolean;
  auto_cover_images: boolean;
  include_citations: boolean;
  human_review_before_publish: boolean;
}

interface ApiGeneralConfig {
  article_length_target: string;
  content_tone: string;
}

// ---- Converters: API (snake_case) → Frontend (camelCase) ----

function toDomain(api: ApiDomain): DomainConfig {
  return {
    id: api.id,
    name: api.name,
    status: api.status,
    trendSources: api.trend_sources as SourceName[],
    keywords: api.keywords,
    articleCount: api.article_count,
  };
}

function toApiKey(api: ApiApiKey): ApiKeyConfig {
  return {
    id: api.id,
    service: api.service,
    maskedKey: api.masked_key,
    status: api.status,
  };
}

function toLlmConfig(api: ApiLlmConfig): LlmConfig {
  return {
    primaryModel: api.primary_model as PrimaryModel,
    draftingModel: api.drafting_model as DraftingModel,
    imageGeneration: api.image_generation as ImageModel,
  };
}

function toSeoDefaults(api: ApiSeoDefaults): SeoDefaults {
  return {
    autoMetaTags: api.auto_meta_tags,
    keywordOptimization: api.keyword_optimization,
    autoCoverImages: api.auto_cover_images,
    includeCitations: api.include_citations,
    humanReviewBeforePublish: api.human_review_before_publish,
  };
}

function toGeneralConfig(api: ApiGeneralConfig): GeneralConfig {
  return {
    articleLengthTarget: api.article_length_target as ArticleLength,
    contentTone: api.content_tone as ContentTone,
  };
}

// ---- Converters: Frontend (camelCase) → API (snake_case) ----

function fromDomain(
  data: Omit<DomainConfig, "id" | "articleCount">,
): Record<string, unknown> {
  return {
    name: data.name,
    status: data.status,
    trend_sources: data.trendSources,
    keywords: data.keywords,
  };
}

function fromLlmConfig(updates: Partial<LlmConfig>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  if (updates.primaryModel !== undefined) out.primary_model = updates.primaryModel;
  if (updates.draftingModel !== undefined) out.drafting_model = updates.draftingModel;
  if (updates.imageGeneration !== undefined) out.image_generation = updates.imageGeneration;
  return out;
}

function fromSeoDefaults(updates: Partial<SeoDefaults>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  if (updates.autoMetaTags !== undefined) out.auto_meta_tags = updates.autoMetaTags;
  if (updates.keywordOptimization !== undefined) out.keyword_optimization = updates.keywordOptimization;
  if (updates.autoCoverImages !== undefined) out.auto_cover_images = updates.autoCoverImages;
  if (updates.includeCitations !== undefined) out.include_citations = updates.includeCitations;
  if (updates.humanReviewBeforePublish !== undefined) out.human_review_before_publish = updates.humanReviewBeforePublish;
  return out;
}

function fromGeneralConfig(updates: Partial<GeneralConfig>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  if (updates.articleLengthTarget !== undefined) out.article_length_target = updates.articleLengthTarget;
  if (updates.contentTone !== undefined) out.content_tone = updates.contentTone;
  return out;
}

// ---- Default fallbacks (used when API unavailable) ----

const DEFAULT_LLM_CONFIG: LlmConfig = {
  primaryModel: "claude-opus-4",
  draftingModel: "claude-sonnet-4",
  imageGeneration: "stable-diffusion-xl",
};

const DEFAULT_SEO_DEFAULTS: SeoDefaults = {
  autoMetaTags: true,
  keywordOptimization: true,
  autoCoverImages: true,
  includeCitations: true,
  humanReviewBeforePublish: true,
};

const DEFAULT_GENERAL_CONFIG: GeneralConfig = {
  articleLengthTarget: "3000-5000",
  contentTone: "professional",
};

// ---- Hook ----

export function useSettings() {
  const [domains, setDomains] = useState<DomainConfig[]>([]);
  const [llmConfig, setLlmConfig] = useState<LlmConfig>(DEFAULT_LLM_CONFIG);
  const [apiKeys, setApiKeys] = useState<ApiKeyConfig[]>([]);
  const [seoDefaults, setSeoDefaults] = useState<SeoDefaults>(DEFAULT_SEO_DEFAULTS);
  const [generalConfig, setGeneralConfig] = useState<GeneralConfig>(DEFAULT_GENERAL_CONFIG);
  const [isLoading, setIsLoading] = useState(true);

  // Load all settings on mount
  useEffect(() => {
    async function loadSettings() {
      setIsLoading(true);
      await Promise.all([
        settingsApi
          .fetchDomains()
          .then((items: ApiDomain[]) => setDomains(items.map(toDomain)))
          .catch(() => console.warn("useSettings: failed to load domains")),
        settingsApi
          .fetchApiKeys()
          .then((items: ApiApiKey[]) => setApiKeys(items.map(toApiKey)))
          .catch(() => console.warn("useSettings: failed to load api keys")),
        settingsApi
          .fetchLlmConfig()
          .then((data: ApiLlmConfig) => setLlmConfig(toLlmConfig(data)))
          .catch(() => console.warn("useSettings: failed to load llm config")),
        settingsApi
          .fetchSeoDefaults()
          .then((data: ApiSeoDefaults) => setSeoDefaults(toSeoDefaults(data)))
          .catch(() => console.warn("useSettings: failed to load seo defaults")),
        settingsApi
          .fetchGeneralConfig()
          .then((data: ApiGeneralConfig) => setGeneralConfig(toGeneralConfig(data)))
          .catch(() => console.warn("useSettings: failed to load general config")),
      ]);
      setIsLoading(false);
    }
    loadSettings();
  }, []);

  const addDomain = useCallback(
    async (data: Omit<DomainConfig, "id" | "articleCount">) => {
      try {
        const created: ApiDomain = await settingsApi.createDomain(
          fromDomain(data) as Parameters<typeof settingsApi.createDomain>[0],
        );
        setDomains((prev) => [...prev, toDomain(created)]);
      } catch {
        console.warn("useSettings: failed to create domain");
      }
    },
    [],
  );

  const updateDomain = useCallback(
    async (id: string, updates: Partial<DomainConfig>) => {
      try {
        // Build snake_case payload from partial camelCase updates
        const payload: Record<string, unknown> = {};
        if (updates.name !== undefined) payload.name = updates.name;
        if (updates.status !== undefined) payload.status = updates.status;
        if (updates.trendSources !== undefined) payload.trend_sources = updates.trendSources;
        if (updates.keywords !== undefined) payload.keywords = updates.keywords;

        const updated: ApiDomain = await settingsApi.updateDomain(id, payload);
        setDomains((prev) =>
          prev.map((d) => (d.id === id ? toDomain(updated) : d)),
        );
      } catch {
        console.warn("useSettings: failed to update domain");
      }
    },
    [],
  );

  const deleteDomain = useCallback(async (id: string) => {
    try {
      await settingsApi.deleteDomain(id);
      setDomains((prev) => prev.filter((d) => d.id !== id));
    } catch {
      console.warn("useSettings: failed to delete domain");
    }
  }, []);

  const updateLlmConfig = useCallback(async (updates: Partial<LlmConfig>) => {
    try {
      const updated: ApiLlmConfig = await settingsApi.updateLlmConfig(
        fromLlmConfig(updates),
      );
      setLlmConfig(toLlmConfig(updated));
    } catch {
      console.warn("useSettings: failed to update llm config");
    }
  }, []);

  const addApiKey = useCallback(
    async (service: ApiKeyService, key: string) => {
      try {
        const created: ApiApiKey = await settingsApi.addApiKey({ service, key });
        setApiKeys((prev) => [...prev, toApiKey(created)]);
      } catch {
        console.warn("useSettings: failed to add api key");
      }
    },
    [],
  );

  const rotateApiKey = useCallback(async (id: string, newKey: string) => {
    try {
      const updated: ApiApiKey = await settingsApi.rotateApiKey(id, { key: newKey });
      setApiKeys((prev) =>
        prev.map((k) => (k.id === id ? toApiKey(updated) : k)),
      );
    } catch {
      console.warn("useSettings: failed to rotate api key");
    }
  }, []);

  const deleteApiKey = useCallback(async (id: string) => {
    try {
      await settingsApi.deleteApiKey(id);
      setApiKeys((prev) => prev.filter((k) => k.id !== id));
    } catch {
      console.warn("useSettings: failed to delete api key");
    }
  }, []);

  const toggleSeoDefault = useCallback(
    async (key: keyof SeoDefaults) => {
      setSeoDefaults((prev) => {
        const next = { ...prev, [key]: !prev[key] };
        settingsApi
          .updateSeoDefaults(fromSeoDefaults({ [key]: next[key] }))
          .then((updated: ApiSeoDefaults) => setSeoDefaults(toSeoDefaults(updated)))
          .catch(() => {
            // Roll back optimistic update on failure
            setSeoDefaults(prev);
            console.warn("useSettings: failed to update seo defaults");
          });
        return next;
      });
    },
    [],
  );

  const updateGeneralConfig = useCallback(
    async (updates: Partial<GeneralConfig>) => {
      try {
        const updated: ApiGeneralConfig = await settingsApi.updateGeneralConfig(
          fromGeneralConfig(updates),
        );
        setGeneralConfig(toGeneralConfig(updated));
      } catch {
        console.warn("useSettings: failed to update general config");
      }
    },
    [],
  );

  return {
    domains,
    llmConfig,
    apiKeys,
    seoDefaults,
    generalConfig,
    isLoading,
    addDomain,
    updateDomain,
    deleteDomain,
    updateLlmConfig,
    addApiKey,
    rotateApiKey,
    deleteApiKey,
    toggleSeoDefault,
    updateGeneralConfig,
  };
}
