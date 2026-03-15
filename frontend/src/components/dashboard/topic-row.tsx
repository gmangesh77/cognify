import { DomainBadge } from "@/components/common/domain-badge";
import { TrendBadge } from "@/components/common/trend-badge";
import type { RankedTopic } from "@/types/api";

interface TopicRowProps {
  topic: RankedTopic;
}

export function TopicRow({ topic }: TopicRowProps) {
  return (
    <div className="flex items-start justify-between border-b border-border px-5 py-3.5 last:border-b-0">
      <div className="min-w-0 flex-1">
        <DomainBadge domain={topic.domain} />
        <p className="mt-1 font-heading text-sm font-medium text-secondary">
          {topic.title}
        </p>
        <div className="mt-2 flex items-center gap-1.5">
          <TrendBadge variant={topic.trend_status} />
          <span className="text-[11px] text-neutral-400">{topic.source}</span>
        </div>
      </div>
      <span className="ml-4 font-heading text-base font-semibold text-neutral-900">
        {topic.composite_score}
      </span>
    </div>
  );
}
