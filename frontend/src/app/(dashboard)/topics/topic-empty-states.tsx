import { Compass, Search } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";

export function SkeletonGrid() {
  return (
    <div className="grid grid-cols-2 gap-6">
      {Array.from({ length: 6 }).map((_, i) => (
        <Skeleton key={i} className="h-44 rounded-lg" />
      ))}
    </div>
  );
}

export function EmptyNoScan() {
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

export function EmptyNoMatch() {
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
