import { useState, useCallback } from "react";
import type { RankedTopic } from "@/types/api";
import { useScanTopics } from "./use-scan-topics";
import { useTopicFilters } from "./use-topic-filters";
import { useTopicPagination } from "./use-topic-pagination";

export function useTopicDiscovery() {
  const { topics, scanState, startScan } = useScanTopics();
  const { filteredTopics, filters, setFilters } = useTopicFilters(topics, {
    timeRange: "7d",
  });
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
  };
}
