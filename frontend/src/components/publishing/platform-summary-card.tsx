import type { PlatformSummary } from "@/types/publishing";

interface PlatformSummaryCardProps {
  summary: PlatformSummary;
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function PlatformSummaryCard({ summary }: PlatformSummaryCardProps) {
  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">
      <h3 className="font-heading text-lg font-semibold text-neutral-800">
        {capitalize(summary.platform)}
      </h3>
      <p className="mt-1 text-3xl font-heading font-semibold text-neutral-900">
        {summary.total}
      </p>
      <p className="mt-1 text-sm text-neutral-500">publications</p>
      <div className="mt-3 flex gap-4 text-xs font-medium">
        <span className="text-green-600">{summary.success} live</span>
        <span className="text-red-600">{summary.failed} failed</span>
        <span className="text-yellow-600">{summary.scheduled} scheduled</span>
      </div>
    </div>
  );
}
