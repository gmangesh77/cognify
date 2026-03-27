"use client";

import { useState } from "react";
import { Send } from "lucide-react";
import { usePublications, usePlatformSummaries, useRetryPublication } from "@/hooks/use-publications";
import { PlatformSummaryCard } from "@/components/publishing/platform-summary-card";
import { PublicationFilters } from "@/components/publishing/publication-filters";
import { PublicationsTable } from "@/components/publishing/publications-table";

export default function PublishingPage() {
  const [platform, setPlatform] = useState("all");
  const [status, setStatus] = useState("all");
  const [page, setPage] = useState(1);

  const filters = {
    platform: platform === "all" ? undefined : platform,
    status: status === "all" ? undefined : status,
    page,
  };

  const { data: pubData, isLoading: pubLoading } = usePublications(filters);
  const { data: summaries, isLoading: sumLoading } = usePlatformSummaries();
  const retryMutation = useRetryPublication();

  const publications = pubData?.items ?? [];
  const total = pubData?.total ?? 0;
  const totalPages = Math.ceil(total / 20);
  const platformNames = summaries?.map((s) => s.platform) ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Send className="h-6 w-6 text-primary" />
        <h1 className="font-heading text-3xl font-semibold text-neutral-800">
          Publishing
        </h1>
      </div>

      {/* Platform summary cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {sumLoading ? (
          <div className="col-span-full text-sm text-neutral-500">Loading platforms...</div>
        ) : summaries && summaries.length > 0 ? (
          summaries.map((s) => <PlatformSummaryCard key={s.platform} summary={s} />)
        ) : (
          <div className="col-span-full rounded-lg border border-neutral-200 bg-white p-6 text-center text-sm text-neutral-500">
            No platforms configured. Publish an article to see platform stats.
          </div>
        )}
      </div>

      {/* Filters */}
      <PublicationFilters
        activePlatform={platform}
        activeStatus={status}
        onPlatformChange={(p) => { setPlatform(p); setPage(1); }}
        onStatusChange={(s) => { setStatus(s); setPage(1); }}
        totalCount={total}
        platforms={platformNames}
      />

      {/* Publications table */}
      {pubLoading ? (
        <div className="text-sm text-neutral-500">Loading publications...</div>
      ) : (
        <PublicationsTable
          publications={publications}
          onRetry={(id) => retryMutation.mutate(id)}
          retryingId={retryMutation.isPending ? (retryMutation.variables ?? null) : null}
        />
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="rounded-md px-3 py-1 text-sm text-neutral-600 hover:bg-neutral-100 disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-sm text-neutral-500">
            Page {page} of {totalPages}
          </span>
          <button
            type="button"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="rounded-md px-3 py-1 text-sm text-neutral-600 hover:bg-neutral-100 disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
