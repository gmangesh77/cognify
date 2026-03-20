import { TrendBadge } from "@/components/common/trend-badge";
import { DomainBadge } from "@/components/common/domain-badge";
import { getSourceLabel } from "@/types/sources";
import type { RankedTopic } from "@/types/api";

interface TopicCardProps {
  topic: RankedTopic;
  onRequestGeneration: (topic: RankedTopic) => void;
}

function formatTimeAgo(dateStr: string): string {
  const hours = Math.floor((Date.now() - new Date(dateStr).getTime()) / 3600000);
  if (hours < 1) return "Just now";
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function TopicCard({ topic, onRequestGeneration }: TopicCardProps) {
  return (
    <div className="flex flex-col justify-between rounded-lg border border-neutral-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md">
      <div>
        <div className="flex items-start justify-between">
          <TrendBadge variant={topic.trend_status} />
          <span className="text-sm font-semibold text-neutral-500">
            Score: <span className="text-neutral-900">{topic.composite_score}</span>
          </span>
        </div>
        <h3 className="mt-3 font-heading text-base font-semibold text-neutral-900">{topic.title}</h3>
        <p className="mt-1.5 line-clamp-2 text-sm text-neutral-500">{topic.description}</p>
      </div>
      <div className="mt-4 flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs text-neutral-400">
          <DomainBadge domain={topic.domain} />
          <span>{getSourceLabel(topic.source)}</span>
          <span>{formatTimeAgo(topic.discovered_at)}</span>
        </div>
        <button onClick={() => onRequestGeneration(topic)} className="text-sm font-medium text-primary hover:underline">
          Generate Article
        </button>
      </div>
    </div>
  );
}
