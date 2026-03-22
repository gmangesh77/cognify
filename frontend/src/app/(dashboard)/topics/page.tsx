"use client";

import { useState } from "react";
import { Zap, Compass, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Header } from "@/components/layout/header";
import { Skeleton } from "@/components/ui/skeleton";
import { TopicCard } from "@/components/topics/topic-card";
import { FilterBar } from "@/components/topics/filter-bar";
import { ScanProgressBanner } from "@/components/topics/scan-progress-banner";
import { TopicPagination } from "@/components/topics/topic-pagination";
import { GenerateArticleModal } from "@/components/topics/generate-article-modal";
import { useTopicDiscovery } from "@/hooks/use-topic-discovery";
import { createResearchSession } from "@/lib/api/trends";

function SkeletonGrid() {
  return (
    <div className="grid grid-cols-2 gap-6">
      {Array.from({ length: 6 }).map((_, i) => (
        <Skeleton key={i} className="h-44 rounded-lg" />
      ))}
    </div>
  );
}

function EmptyNoScan() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <Compass className="mb-4 h-12 w-12 text-neutral-300" />
      <h3 className="font-heading text-lg font-semibold text-neutral-700">
        No topics discovered yet
      </h3>
      <p className="mt-2 max-w-sm text-sm text-neutral-500">
        Select a domain from the filter bar, then click &ldquo;New Scan&rdquo; to discover
        trending topics from all configured sources.
      </p>
    </div>
  );
}

function EmptyNoMatch() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <Search className="mb-4 h-12 w-12 text-neutral-300" />
      <h3 className="font-heading text-lg font-semibold text-neutral-700">
        No topics match your filters
      </h3>
      <p className="mt-2 max-w-sm text-sm text-neutral-500">
        Try adjusting the source, time range, or domain filters to see more results.
      </p>
    </div>
  );
}

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
  } = useTopicDiscovery();

  const [toast, setToast] = useState<string | null>(null);

  const isScanning = scanState.isScanning;
  const hasDomain = filters.domain !== "";
  const hasScanResult = !isScanning && (topics.length > 0 || totalTopics > 0);
  const scanHasEverRun = hasScanResult || scanState.completedSources > 0;

  const showSkeletons = isScanning && topics.length === 0;
  const showEmptyNoScan = !isScanning && !scanHasEverRun;
  const showEmptyNoMatch = !isScanning && scanHasEverRun && totalTopics === 0;
  const showGrid = topics.length > 0;

  async function handleConfirm() {
    const topic = modalTopic;
    closeModal();
    if (!topic) return;
    if (!topic.id) {
      setToast(`Cannot start research — topic has no ID. Try scanning again.`);
      setTimeout(() => setToast(null), 5000);
      return;
    }
    setToast(`Starting research for "${topic.title}"...`);
    try {
      await createResearchSession(topic.id);
      setToast(
        `Research started for "${topic.title}". Check Research page for progress.`,
      );
    } catch {
      setToast(`Failed to start research for "${topic.title}".`);
    }
    setTimeout(() => setToast(null), 5000);
  }

  return (
    <div className="space-y-8">
      <Header
        title="Topic Discovery"
        subtitle="Browse trending topics and trigger research and content generation."
      >
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
              key={topic.rank}
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
        onConfirm={handleConfirm}
      />

      {toast && (
        <div
          role="status"
          className="fixed bottom-6 right-6 z-50 rounded-lg bg-neutral-900 px-4 py-3 text-sm text-white shadow-lg"
        >
          {toast}
        </div>
      )}
    </div>
  );
}
