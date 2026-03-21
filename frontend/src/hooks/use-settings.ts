import { useState, useCallback } from "react";
import type {
  DomainConfig,
  LlmConfig,
  ApiKeyConfig,
  ApiKeyService,
  SeoDefaults,
  GeneralConfig,
} from "@/types/settings";
import {
  mockDomains,
  mockLlmConfig,
  mockApiKeys,
  mockSeoDefaults,
  mockGeneralConfig,
} from "@/lib/mock/settings";

function maskKey(key: string): string {
  const prefix = key.slice(0, 4);
  const suffix = key.slice(-4);
  return `${prefix}-••••••••${suffix}`;
}

export function useSettings() {
  const [domains, setDomains] = useState<DomainConfig[]>(mockDomains);
  const [llmConfig, setLlmConfig] = useState<LlmConfig>(mockLlmConfig);
  const [apiKeys, setApiKeys] = useState<ApiKeyConfig[]>(mockApiKeys);
  const [seoDefaults, setSeoDefaults] = useState<SeoDefaults>(mockSeoDefaults);
  const [generalConfig, setGeneralConfig] = useState<GeneralConfig>(mockGeneralConfig);

  const addDomain = useCallback(
    (data: Omit<DomainConfig, "id" | "articleCount">) => {
      const newDomain: DomainConfig = {
        ...data,
        id: `dom-${Date.now()}`,
        articleCount: 0,
      };
      setDomains((prev) => [...prev, newDomain]);
    },
    [],
  );

  const updateDomain = useCallback(
    (id: string, updates: Partial<DomainConfig>) => {
      setDomains((prev) =>
        prev.map((d) => (d.id === id ? { ...d, ...updates } : d)),
      );
    },
    [],
  );

  const deleteDomain = useCallback((id: string) => {
    setDomains((prev) => prev.filter((d) => d.id !== id));
  }, []);

  const updateLlmConfig = useCallback((updates: Partial<LlmConfig>) => {
    setLlmConfig((prev) => ({ ...prev, ...updates }));
  }, []);

  const addApiKey = useCallback((service: ApiKeyService, key: string) => {
    const newKey: ApiKeyConfig = {
      id: `key-${Date.now()}`,
      service,
      maskedKey: maskKey(key),
      status: "active",
    };
    setApiKeys((prev) => [...prev, newKey]);
  }, []);

  const rotateApiKey = useCallback((id: string, newKey: string) => {
    setApiKeys((prev) =>
      prev.map((k) =>
        k.id === id ? { ...k, maskedKey: maskKey(newKey) } : k,
      ),
    );
  }, []);

  const toggleSeoDefault = useCallback((key: keyof SeoDefaults) => {
    setSeoDefaults((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  const updateGeneralConfig = useCallback((updates: Partial<GeneralConfig>) => {
    setGeneralConfig((prev) => ({ ...prev, ...updates }));
  }, []);

  return {
    domains,
    llmConfig,
    apiKeys,
    seoDefaults,
    generalConfig,
    addDomain,
    updateDomain,
    deleteDomain,
    updateLlmConfig,
    addApiKey,
    rotateApiKey,
    toggleSeoDefault,
    updateGeneralConfig,
  };
}
