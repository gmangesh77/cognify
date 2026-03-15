import Link from "next/link";
import { Skeleton } from "@/components/ui/skeleton";
import { TopicRow } from "./topic-row";
import type { RankedTopic } from "@/types/api";

interface TrendingTopicsListProps {
  topics: RankedTopic[];
  isLoading: boolean;
  isError?: boolean;
  onRetry?: () => void;
}

export function TrendingTopicsList({ topics, isLoading, isError, onRetry }: TrendingTopicsListProps) {
  return (
    <div className="rounded-md border border-border bg-white shadow-md">
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <h2 className="font-heading text-base font-semibold text-neutral-900">Trending Topics</h2>
        <Link href="/topics" className="text-sm font-medium text-primary hover:text-primary/80">
          View All
        </Link>
      </div>
      {isLoading && (
        <div className="space-y-0">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="border-b border-border px-5 py-3.5 last:border-b-0">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="mt-2 h-4 w-3/4" />
              <Skeleton className="mt-2 h-3 w-1/3" />
            </div>
          ))}
        </div>
      )}
      {isError && (
        <div className="px-5 py-10 text-center">
          <p className="text-sm text-neutral-500">Unable to load trending topics</p>
          {onRetry && (
            <button onClick={onRetry} className="mt-2 text-sm font-medium text-primary hover:text-primary/80">
              Retry
            </button>
          )}
        </div>
      )}
      {!isLoading && !isError && topics.length === 0 && (
        <div className="px-5 py-10 text-center">
          <p className="text-sm text-neutral-500">No trending topics found. Try adjusting your domain keywords.</p>
        </div>
      )}
      {!isLoading && !isError && topics.length > 0 && (
        <div>
          {topics.map((topic) => (
            <TopicRow key={`${topic.rank}-${topic.title}`} topic={topic} />
          ))}
        </div>
      )}
    </div>
  );
}
