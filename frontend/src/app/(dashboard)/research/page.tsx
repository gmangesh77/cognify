"use client";

import { useState } from "react";
import { Header } from "@/components/layout/header";
import { Skeleton } from "@/components/ui/skeleton";
import { SessionCard } from "@/components/research/session-card";
import { SessionSteps } from "@/components/research/session-steps";
import { SessionFilters } from "@/components/research/session-filters";
import { KnowledgeBaseStub } from "@/components/research/knowledge-base-stub";
import { TopicPagination } from "@/components/topics/topic-pagination";
import { useResearchSessions, useResearchSession } from "@/hooks/use-research-sessions";
import type { SessionStatus } from "@/types/research";

const PAGE_SIZE = 10;

export default function ResearchPage() {
  const [activeFilter, setActiveFilter] = useState<SessionStatus | "all">("all");
  const [expandedSessionId, setExpandedSessionId] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);

  const sessionsQuery = useResearchSessions(
    activeFilter === "all" ? undefined : activeFilter,
    currentPage,
    PAGE_SIZE,
  );
  const detailQuery = useResearchSession(expandedSessionId);

  function handleFilterChange(filter: SessionStatus | "all") {
    setActiveFilter(filter);
    setCurrentPage(1);
    setExpandedSessionId(null);
  }

  function handleToggle(sessionId: string) {
    setExpandedSessionId((prev) => (prev === sessionId ? null : sessionId));
  }

  const sessions = sessionsQuery.data?.items ?? [];
  const totalCount = sessionsQuery.data?.total ?? 0;
  const totalPages = Math.ceil(totalCount / PAGE_SIZE);

  return (
    <div className="space-y-6">
      <Header title="Research Sessions" subtitle="Monitor agent research workflows" />

      <SessionFilters
        activeFilter={activeFilter}
        onFilterChange={handleFilterChange}
        totalCount={totalCount}
      />

      {sessionsQuery.isLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full rounded-lg" />
          ))}
        </div>
      ) : sessions.length === 0 ? (
        <div className="rounded-lg border border-dashed border-neutral-300 bg-neutral-50 py-12 text-center">
          <p className="text-sm text-neutral-500">No research sessions found.</p>
          <p className="mt-1 text-xs text-neutral-400">
            {activeFilter !== "all"
              ? `No sessions with status "${activeFilter}". Try a different filter.`
              : "Start a research session from Topic Discovery."}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {sessions.map((session) => (
            <SessionCard
              key={session.session_id}
              session={session}
              isExpanded={expandedSessionId === session.session_id}
              onToggle={() => handleToggle(session.session_id)}
            >
              <SessionSteps
                steps={detailQuery.data?.steps ?? []}
                isLoading={detailQuery.isLoading}
              />
            </SessionCard>
          ))}
        </div>
      )}

      <KnowledgeBaseStub />

      {totalPages > 1 && (
        <TopicPagination
          currentPage={currentPage}
          totalPages={totalPages}
          onPageChange={setCurrentPage}
        />
      )}
    </div>
  );
}
