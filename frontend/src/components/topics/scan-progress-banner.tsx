interface ScanProgressBannerProps {
  isScanning: boolean;
  completedSources: number;
  totalSources: number;
  failedSources: string[];
}

export function ScanProgressBanner({
  isScanning,
  completedSources,
  totalSources,
  failedSources,
}: ScanProgressBannerProps) {
  const hasFailures = !isScanning && failedSources.length > 0;
  if (!isScanning && !hasFailures) return null;

  if (hasFailures) {
    return (
      <div className="rounded-lg border border-accent/30 bg-accent-light px-4 py-3 text-sm text-accent">
        {failedSources.length} of {totalSources} sources failed to respond. Results may be incomplete.
      </div>
    );
  }

  const pct = Math.round((completedSources / totalSources) * 100);
  return (
    <div className="rounded-lg border border-info/30 bg-info-light px-4 py-3">
      <div className="flex items-center justify-between text-sm text-info">
        <span>Scanning... {completedSources} of {totalSources} sources complete</span>
        <span>{pct}%</span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-info/20">
        <div className="h-full rounded-full bg-info transition-all" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
