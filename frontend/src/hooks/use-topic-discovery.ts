import { useState, useCallback, useEffect, useMemo } from "react";
import type { RankedTopic } from "@/types/api";
import { useScanTopics } from "./use-scan-topics";
import { useTopicFilters } from "./use-topic-filters";
import { useTopicPagination } from "./use-topic-pagination";
import { fetchDomains } from "@/lib/api/settings";

interface ApiDomain {
  id: string;
  name: string;
  status: "active" | "inactive";
  trend_sources: string[];
  keywords: string[];
  article_count: number;
}

export function useTopicDiscovery() {
  const [apiDomains, setApiDomains] = useState<ApiDomain[]>([]);

  // Load saved domains from settings API on mount
  useEffect(() => {
    fetchDomains()
      .then((items: ApiDomain[]) => setApiDomains(items))
      .catch(() => {
        // Fall back to hardcoded domains when API unavailable
      });
  }, []);

  // Build a domain → keywords map from saved settings for use during scans
  const dynamicKeywords = useMemo<Record<string, string[]>>(() => {
    if (apiDomains.length === 0) return {};
    return Object.fromEntries(
      apiDomains.map((d) => [d.name.toLowerCase().replace(/\s+/g, "-"), d.keywords]),
    );
  }, [apiDomains]);

  // Build a domain slug → display label map for the filter bar dropdown
  const domainOptions = useMemo<Record<string, string>>(() => {
    if (apiDomains.length === 0) return {};
    return Object.fromEntries(
      apiDomains.map((d) => [d.name.toLowerCase().replace(/\s+/g, "-"), d.name]),
    );
  }, [apiDomains]);

  const { topics, scanState, startScan } = useScanTopics(
    Object.keys(dynamicKeywords).length > 0 ? dynamicKeywords : undefined,
  );
  const { filteredTopics, filters, setFilters } = useTopicFilters(topics);
  const { paginatedItems, page, totalPages, setPage } =
    useTopicPagination(filteredTopics);

  const [modalTopic, setModalTopic] = useState<RankedTopic | null>(null);
  const openModal = useCallback((t: RankedTopic) => setModalTopic(t), []);
  const closeModal = useCallback(() => setModalTopic(null), []);

  return {
    topics: paginatedItems,
    totalTopics: filteredTopics.length,
    scanState,
    startScan,
    filters,
    setFilters,
    page,
    totalPages,
    setPage,
    modalTopic,
    openModal,
    closeModal,
    /** Pass to FilterBar so the domain dropdown reflects saved settings */
    domainOptions: Object.keys(domainOptions).length > 0 ? domainOptions : undefined,
  };
}
