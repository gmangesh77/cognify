import { Button } from "@/components/ui/button";
import { TrendBadge } from "@/components/common/trend-badge";
import { DomainBadge } from "@/components/common/domain-badge";
import type { RankedTopic } from "@/types/api";

interface GenerateArticleModalProps {
  topic: RankedTopic | null;
  onClose: () => void;
  onConfirm: (topic: RankedTopic) => void;
}

export function GenerateArticleModal({ topic, onClose, onConfirm }: GenerateArticleModalProps) {
  if (!topic) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      <div
        role="dialog"
        className="w-full max-w-md rounded-xl bg-white p-6 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="font-heading text-lg font-semibold text-neutral-900">Generate Article</h2>
        <div className="mt-4 space-y-3">
          <div className="flex items-center gap-2">
            <TrendBadge variant={topic.trend_status} />
            <DomainBadge domain={topic.domain} />
          </div>
          <h3 className="font-heading text-base font-medium text-neutral-900">{topic.title}</h3>
          <p className="text-sm text-neutral-500">{topic.description}</p>
          <p className="text-sm text-neutral-500">
            Score: <span className="font-semibold text-neutral-900">{topic.composite_score}</span>
          </p>
        </div>
        <p className="mt-4 text-sm text-neutral-500">
          This will start the content generation pipeline. Estimated time: 2-5 minutes.
        </p>
        <div className="mt-6 flex justify-end gap-3">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={() => onConfirm(topic)}>Generate</Button>
        </div>
      </div>
    </div>
  );
}
