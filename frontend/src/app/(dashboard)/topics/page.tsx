"use client";

import { useState } from "react";
import { Zap, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toaster";
import { Header } from "@/components/layout/header";
import { TopicCard } from "@/components/topics/topic-card";
import { FilterBar } from "@/components/topics/filter-bar";
import { ScanProgressBanner } from "@/components/topics/scan-progress-banner";
import { TopicPagination } from "@/components/topics/topic-pagination";
import { GenerateArticleModal } from "@/components/topics/generate-article-modal";
import { CreateTopicModal, type CreateTopicData } from "@/components/topics/create-topic-modal";
import { useTopicDiscovery } from "@/hooks/use-topic-discovery";
import { createManualTopic } from "@/lib/api/trends";
import { useGenerateActions } from "./use-generate-actions";
import { SkeletonGrid, EmptyNoScan, EmptyNoMatch } from "./topic-empty-states";
import type { ArticleParams, RankedTopic } from "@/types/api";

export default function TopicsPage() {
  const {
    topics,
    totalTopics,
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
    domainOptions,
  } = useTopicDiscovery();

  const { showToast } = useToast();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const { handleConfirm, handleCreateAndGenerate } = useGenerateActions({ showToast });

  const isScanning = scanState.isScanning;
  const hasDomain = filters.domain !== "";
  const hasScanResult = !isScanning && (topics.length > 0 || totalTopics > 0);
  const scanHasEverRun = hasScanResult || scanState.completedSources > 0;

  const showSkeletons = isScanning && topics.length === 0;
  const showEmptyNoScan = !isScanning && !scanHasEverRun;
  const showEmptyNoMatch = !isScanning && scanHasEverRun && totalTopics === 0;
  const showGrid = topics.length > 0;

  async function handleCreateOnly(data: CreateTopicData) {
    setShowCreateModal(false);
    try {
      const result = await createManualTopic({
        title: data.title,
        description: data.description,
        domain: data.domain,
        keywords: data.keywords,
      });
      if (result.is_duplicate) {
        showToast(`Similar topic already exists: "${result.topic.title}"`);
      } else {
        showToast(`Topic "${data.title}" created.`);
      }
    } catch {
      showToast(`Failed to create topic.`);
    }
  }

  function onCreateAndGenerate(data: CreateTopicData) {
    setShowCreateModal(false);
    void handleCreateAndGenerate(data);
  }

  function onConfirmGenerate(topic: RankedTopic, articleParams?: ArticleParams) {
    closeModal();
    void handleConfirm(topic, articleParams);
  }

  return (
    <div className="space-y-8">
      <Header
        title="Topic Discovery"
        subtitle="Browse trending topics and trigger research and content generation."
      >
        <Button
          size="sm"
          variant="outline"
          onClick={() => setShowCreateModal(true)}
        >
          <Plus className="mr-2 h-4 w-4" />
          Create Topic
        </Button>
        <Button
          size="sm"
          className="bg-primary hover:bg-primary/90"
          disabled={isScanning || !hasDomain}
          onClick={() => startScan(filters.domain)}
        >
          <Zap className="mr-2 h-4 w-4" />
          New Scan
        </Button>
      </Header>

      <FilterBar
        filters={filters}
        onFilterChange={setFilters}
        topicCount={totalTopics}
        domainOptions={domainOptions}
      />

      <ScanProgressBanner
        isScanning={isScanning}
        completedSources={scanState.completedSources}
        totalSources={scanState.totalSources}
        failedSources={scanState.failedSources}
      />

      {showSkeletons && <SkeletonGrid />}
      {showEmptyNoScan && <EmptyNoScan />}
      {showEmptyNoMatch && <EmptyNoMatch />}

      {showGrid && (
        <div className="grid grid-cols-2 gap-6">
          {topics.map((topic) => (
            <TopicCard
              key={topic.id ?? `${topic.source}:${topic.external_url}`}
              topic={topic}
              onRequestGeneration={openModal}
            />
          ))}
        </div>
      )}

      <TopicPagination
        currentPage={page}
        totalPages={totalPages}
        onPageChange={setPage}
      />

      <GenerateArticleModal
        topic={modalTopic}
        onClose={closeModal}
        onConfirm={onConfirmGenerate}
      />

      <CreateTopicModal
        open={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreateOnly={handleCreateOnly}
        onCreateAndGenerate={onCreateAndGenerate}
      />

    </div>
  );
}
